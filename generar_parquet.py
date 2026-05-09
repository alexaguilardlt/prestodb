import pandas as pd
import numpy as np
import os

# Asegurar que la carpeta data_lake existe
os.makedirs('data_lake/productos', exist_ok=True)

# Crear 1000 productos falsos
num_productos = 1000
datos = {
    'id_producto': range(1, num_productos + 1),
    'categoria': np.random.choice(['Electronica', 'Ropa', 'Hogar', 'Deportes', 'Juguetes'], num_productos),
    'marca': np.random.choice(['MarcaA', 'MarcaB', 'MarcaC', 'Generica'], num_productos),
}

df = pd.DataFrame(datos)

# Guardar como archivo Parquet
df.to_parquet('data_lake/productos/datos.parquet', index=False)
print("Archivo Parquet generado con éxito en data_lake/productos/datos.parquet")