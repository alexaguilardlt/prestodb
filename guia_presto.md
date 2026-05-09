***

# Guía Paso a Paso: Despliegue de Consultas Federadas con PrestoDB

Esta guía detalla los pasos exactos para levantar el entorno local, generar los datos de prueba y ejecutar la consulta federada requerida para la Actividad AA5. 



## Requisitos Previos
Antes de empezar, cada miembro del equipo debe asegurarse de tener instalado en su ordenador:
1. **Docker Desktop** (o Docker Engine + Docker Compose).
2. **Python 3** (con las librerías `pandas` y `pyarrow` instaladas para generar el archivo Parquet).
   * Comando de instalación: `pip install pandas pyarrow`

---

## FASE 1: Estructura de Carpetas y Configuración

PrestoDB es muy estricto con los archivos de configuración para gestionar la memoria (evitando errores *Out of Memory*). Debemos crear la siguiente estructura de carpetas exactamente como se muestra aquí, en la raíz del proyecto:

```text
/vuestro-repo
├── docker-compose.yml
├── generar_parquet.py
├── /data_lake
│   └── /productos
├── /presto_coordinator_etc
│   ├── config.properties
│   ├── jvm.config
│   ├── node.properties
│   └── /catalog
│       ├── hive.properties
│       └── postgresql.properties
├── /presto_worker_1_etc
│   └── (mismos 5 archivos que el coordinator, cambiando node.properties y config.properties)
└── /presto_worker_2_etc
    └── (mismos 5 archivos, cambiando node.properties y config.properties)
```

### 1.1 Archivos de Configuración Base
Crea estos archivos dentro de sus carpetas correspondientes:

**En `presto_coordinator_etc/`:**
* `node.properties`:
  ```properties
  node.environment=produccion
  node.id=coordinator
  node.data-dir=/var/presto/data
  ```
* `jvm.config`:
  
```text
  -server
  -Xmx1G
  -XX:+UseG1GC
  -XX:G1HeapRegionSize=32M
  -XX:+UseGCOverheadLimit
  -XX:+ExplicitGCInvokesConcurrent
  -XX:+HeapDumpOnOutOfMemoryError
  -XX:+ExitOnOutOfMemoryError
  ```
* `config.properties`:
  
```properties
  coordinator=true
  node-scheduler.include-coordinator=false
  http-server.http.port=8080
  query.max-memory=2GB
  query.max-memory-per-node=1GB
  discovery-server.enabled=true
  discovery.uri=http://presto_coordinator:8080
  ```

**En `presto_worker_1_etc/`:**
Copia el `jvm.config` exacto del coordinator. Los otros dos cambian:
* `node.properties`:
  
```properties
  node.environment=produccion
  node.id=worker1
  node.data-dir=/var/presto/data
  ```
* `config.properties`:
  
```properties
  coordinator=false
  http-server.http.port=8080
  query.max-memory=2GB
  query.max-memory-per-node=1GB
  discovery.uri=http://presto_coordinator:8080
  ```

**En `presto_worker_2_etc/`:**
Copia todo lo del Worker 1, pero cambia el ID en `node.properties`:
* `node.properties`:
  
```properties
  node.environment=produccion
  node.id=worker2
  node.data-dir=/var/presto/data
  ```

### 1.2 Archivos de Catálogo (Conectores)
Dentro de la carpeta `catalog` de **los tres nodos** (Coordinator, Worker 1 y Worker 2), debes crear estos dos archivos. Son los que dicen a Presto dónde están los datos:

* `postgresql.properties`:
  
```properties
  connector.name=postgresql
  connection-url=jdbc:postgresql://postgres:5432/ecommercedb
  connection-user=presto_user
  connection-password=presto_password
  ```
* `hive.properties`:
  
```properties
  connector.name=hive-hadoop2
  hive.metastore=file
  hive.metastore.catalog.dir=/var/presto/data_lake
  ```

---

## FASE 2: Infraestructura con Docker

Crea el archivo `docker-compose.yml` en la raíz del proyecto con el siguiente código para orquestar la Base de Datos Transaccional y el Clúster de Presto.

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: postgres_fuente_a
    environment:
      POSTGRES_USER: presto_user
      POSTGRES_PASSWORD: presto_password
      POSTGRES_DB: ecommercedb
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - presto-cluster-net

  presto-coordinator:
    image: prestodb/presto:latest
    container_name: presto_coordinator
    ports:
      - "8080:8080"
    volumes:
      - ./presto_coordinator_etc:/opt/presto-server/etc
      - ./data_lake:/var/presto/data_lake
    command: ["/opt/presto-server/bin/launcher", "run"]
    networks:
      - presto-cluster-net
    depends_on:
      - postgres

  presto-worker-1:
    image: prestodb/presto:latest
    container_name: presto_worker_1
    volumes:
      - ./presto_worker_1_etc:/opt/presto-server/etc
      - ./data_lake:/var/presto/data_lake
    command: ["/opt/presto-server/bin/launcher", "run"]
    networks:
      - presto-cluster-net
    depends_on:
      - presto-coordinator

  presto-worker-2:
    image: prestodb/presto:latest
    container_name: presto_worker_2
    volumes:
      - ./presto_worker_2_etc:/opt/presto-server/etc
      - ./data_lake:/var/presto/data_lake
    command: ["/opt/presto-server/bin/launcher", "run"]
    networks:
      - presto-cluster-net
    depends_on:
      - presto-coordinator

networks:
  presto-cluster-net:
    driver: bridge

volumes:
  pgdata:
```

**Comando para levantar la infraestructura:**
Abre una terminal en la raíz del proyecto y ejecuta:
```bash
docker-compose up -d
```
*(Puedes verificar que funciona entrando en `http://localhost:8080` en tu navegador. Deberías ver la interfaz de Presto y "Active Workers: 2").*

---

## FASE 3: Generación de Datos

Vamos a crear nuestras dos fuentes de datos heterogéneas.

### 3.1 Fuente A: PostgreSQL (Datos Transaccionales)
Generaremos 100.000 registros de ventas. Ejecuta esto en la terminal para entrar a la base de datos:
```bash
docker exec -it postgres_fuente_a psql -U presto_user -d ecommercedb
```
Una vez dentro (en el prompt `ecommercedb=#`), pega el siguiente SQL:
```sql
CREATE TABLE ventas (
    id_venta SERIAL PRIMARY KEY,
    id_producto INT NOT NULL,
    cantidad INT NOT NULL,
    precio_total DECIMAL(10,2) NOT NULL,
    fecha_venta DATE NOT NULL
);

INSERT INTO ventas (id_producto, cantidad, precio_total, fecha_venta)
SELECT 
    (random() * 999 + 1)::INT,
    (random() * 4 + 1)::INT,
    (random() * 100 + 10)::DECIMAL(10,2),
    CURRENT_DATE - (random() * 365)::INT
FROM generate_series(1, 100000);
```
Escribe `\q` y pulsa Enter para salir.

### 3.2 Fuente B: Data Lake (Archivo Parquet)
Crea un archivo llamado `generar_parquet.py` en la raíz del proyecto:
```python
import pandas as pd
import numpy as np
import os

os.makedirs('data_lake/productos', exist_ok=True)

num_productos = 1000
datos = {
    'id_producto': range(1, num_productos + 1),
    'categoria': np.random.choice(['Electronica', 'Ropa', 'Hogar', 'Deportes', 'Juguetes'], num_productos),
    'marca': np.random.choice(['MarcaA', 'MarcaB', 'MarcaC', 'Generica'], num_productos),
}

df = pd.DataFrame(datos)
df.to_parquet('data_lake/productos/datos.parquet', index=False)
print("Archivo Parquet generado.")
```
Ejecútalo desde tu terminal local:
```bash
python generar_parquet.py
```

> **IMPORTANTE:** Si acabas de generar los catálogos ahora, reinicia el clúster para que Presto los detecte:
> ```bash
> docker-compose restart
> ```

---

## FASE 4: Ejecución en PrestoDB

Vamos a entrar en la consola de comandos (CLI) de Presto para cruzar los datos.

Entra al Coordinator ejecutando:
```bash
docker exec -it presto_coordinator presto-cli --catalog hive --schema default
```

### 4.1 Mapear el archivo Parquet
Para que Presto entienda el archivo `.parquet`, debemos crear la definición de la tabla. 
*Nota sobre el tipo de dato: Usamos `BIGINT` porque la librería de Python genera por defecto enteros de 64 bits. Usar `INTEGER` daría error de incompatibilidad.*

Pega esto en la consola de Presto:
```sql
CREATE TABLE productos_v2 (
    id_producto BIGINT,
    categoria VARCHAR,
    marca VARCHAR
) WITH (
    format = 'PARQUET',
    external_location = 'file:///var/presto/data_lake/productos/'
);
```

### 4.2 Comprobación (Opcional)
Asegúrate de que Presto lee el Parquet correctamente:
```sql
SELECT * FROM productos_v2 LIMIT 5;
```

### 4.3 Consulta Federada (KPI del Negocio)
Esta es la consulta principal que calcula el total de ingresos cruzando Postgres (ventas) con el archivo Parquet (categorías de producto). **Esta consulta es la que se debe mostrar en el vídeo.**

```sql
SELECT 
    p.categoria,
    SUM(v.cantidad) AS total_unidades_vendidas,
    SUM(v.precio_total) AS ingresos_totales
FROM postgresql.public.ventas v
JOIN hive.default.productos_v2 p ON v.id_producto = p.id_producto
GROUP BY p.categoria
ORDER BY ingresos_totales DESC;
```

### 4.4 Análisis de Plan de Ejecución (Pushdown)
Para cumplir con la rúbrica y ver cómo Presto optimiza filtrando los datos en origen (Predicate Pushdown), ejecutamos el plan con `EXPLAIN`:

```sql
EXPLAIN 
SELECT 
    p.categoria,
    SUM(v.precio_total) AS ingresos_totales
FROM postgresql.public.ventas v
JOIN hive.default.productos_v2 p ON v.id_producto = p.id_producto
WHERE v.fecha_venta > DATE '2025-01-01'
GROUP BY p.categoria;
```
*(Salimos de la CLI escribiendo `quit` y pulsando Enter).*

---

## FASE 5: Recopilación de Evidencias
Tras ejecutar las consultas, entra inmediatamente en `http://localhost:8080`.
1. Haz una captura de pantalla a la lista principal con las queries marcadas como `FINISHED`.
2. Haz clic en el código de la consulta federada y haz una captura a la pestaña `Live Plan` mostrando los "Splits" distribuidos. 
*(Estas capturas van obligatoriamente al documento .pdf final).*
```