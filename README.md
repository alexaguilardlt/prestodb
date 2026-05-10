# Actividad 5 - Presto + PostgreSQL con Docker Compose
Este proyecto levanta un clúster de Presto (1 coordinator + 2 workers) y una base PostgreSQL para consultas federadas.

## Requisitos
- Docker Desktop en ejecución
- Docker Compose v2

## Estructura relevante
- `docker-compose.yml`
- `presto_coordinator_etc/`
- `presto_worker_1_etc/`
- `presto_worker_2_etc/`
- `data_lake/`

## Levantar el stack
```bash
docker-compose up -d
```

## Reiniciar desde cero
```bash
docker-compose down
docker-compose up -d
```

## Verificar estado
1. Estado de contenedores:
```bash
docker-compose ps -a
```
2. Salud del coordinator:
```bash
curl -sSf http://localhost:8080/v1/info
```
Debe devolver JSON con `"coordinator": true` y `"starting": false`.

3. Registro de workers en el coordinator:
```bash
curl -sSf http://localhost:8080/v1/node
```
Debe listar 2 nodos worker.

## Cambios de configuración aplicados
- Montajes de workers corregidos en `docker-compose.yml`:
  - `presto-worker-1` -> `./presto_worker_1_etc:/opt/presto-server/etc`
  - `presto-worker-2` -> `./presto_worker_2_etc:/opt/presto-server/etc`
- `discovery.uri` unificado a `http://presto-coordinator:8080`.
- Se añadió `-Djdk.attach.allowAttachSelf=true` en `jvm.config` de coordinator y workers.
- Ajuste de memoria para evitar fallo de arranque de Presto:
  - `query.max-memory=1GB` (coordinator)
  - `query.max-memory-per-node=512MB`
  - `query.max-total-memory-per-node=512MB`

## Logs útiles
```bash
docker-compose logs --no-color --timestamps --tail=200 presto-coordinator presto-worker-1 presto-worker-2
```
## Consultas Federadas

Ejemplo de consulta federada:

```sql
SELECT 
    p.categoria,
    SUM(v.cantidad) AS total_unidades_vendidas,
    ROUND(SUM(v.precio_total),2) AS ingresos_totales
FROM postgresql.public.ventas v
JOIN hive.default.productos_v2 p 
    ON v.id_producto = p.id_producto
GROUP BY p.categoria
ORDER BY ingresos_totales DESC;
```

## Apagar stack
```bash
docker-compose down
```
