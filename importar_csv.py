#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Importación Masiva desde CSV
Sistema de Gestión Comercial - CLF Yucateca

FORMATOS DE CSV ESPERADOS:
===========================

1. CLIENTES.csv:
nombre_comercial,razon_social,tipo,rfc,direccion,contacto,telefono,email

2. PRODUCTOS.csv:
ID,CODIGO,DESCRIPCION,CATEGORIA,SUBCATEGORIA,UNIDAD,COSTO,IVA,PRECIO,STOCK,STOCK MIN

Ejemplo:
,CAF001,Café Nescafé Clásico 200g,Café,Café Soluble,Pieza,85.50,SI,120.00,100,20

3. CATEGORIAS.csv:
nombre

Notas importantes:
- Los archivos deben estar en la misma carpeta que este script
- La primera línea debe tener los encabezados (se ignora automáticamente)
- Usa comas (,) como separador
- Si un campo tiene comas, enciérralo entre comillas: "Producto, modelo A"
- Para PRODUCTOS.csv:
  * ID: Déjalo vacío, el sistema genera IDs automáticamente
  * CODIGO: Debe ser único (ej: CAF001, VAS002)
  * DESCRIPCION: Nombre completo del producto
  * CATEGORIA y SUBCATEGORIA: Se crean automáticamente si no existen
  * UNIDAD: Pieza, Caja, Kg, Litro, Paquete, etc.
  * COSTO: Tu precio de compra (sin símbolos $)
  * IVA: SI o NO (también acepta S/N, 1/0)
  * PRECIO: Precio de venta (opcional, puede dejarse en 0)
  * STOCK: Cantidad actual en inventario
  * STOCK MIN: Nivel mínimo para alertas
"""

import csv
import sqlite3
import os
from datetime import datetime

class ImportadorCSV:
    """Clase para importar datos desde archivos CSV"""
    
    def __init__(self, db_path='gestion_comercial.db'):
        """
        Inicializa el importador
        
        Args:
            db_path: Ruta a la base de datos
        """
        if not os.path.exists(db_path):
            print(f"❌ ERROR: La base de datos '{db_path}' no existe.")
            print("Por favor ejecuta primero 'main.py' para crear la base de datos.\n")
            return None
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        print(f"✓ Conectado a la base de datos: {db_path}\n")
    
    def importar_categorias(self, archivo_csv='CATEGORIAS.csv'):
        """
        Importa categorías desde CSV
        
        Formato esperado:
        nombre
        Café
        Equipo
        Desechables
        
        Args:
            archivo_csv: Ruta al archivo CSV
        
        Returns:
            Número de categorías importadas
        """
        if not os.path.exists(archivo_csv):
            print(f"⚠️  Archivo '{archivo_csv}' no encontrado. Saltando...")
            return 0
        
        print(f"📂 Importando categorías desde '{archivo_csv}'...")
        
        insertadas = 0
        duplicadas = 0
        errores = 0
        
        try:
            with open(archivo_csv, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                for i, row in enumerate(reader, start=2):  # Empezar en 2 (línea 1 son encabezados)
                    try:
                        nombre = row.get('nombre', '').strip()
                        
                        if not nombre:
                            print(f"   ⚠️  Línea {i}: Nombre vacío, saltando...")
                            continue
                        
                        self.cursor.execute(
                            "INSERT INTO categorias (nombre) VALUES (?)",
                            (nombre,)
                        )
                        insertadas += 1
                        print(f"   ✓ {nombre}")
                        
                    except sqlite3.IntegrityError:
                        duplicadas += 1
                        print(f"   - {nombre} (ya existe)")
                    except Exception as e:
                        errores += 1
                        print(f"   ✗ Línea {i}: Error - {str(e)}")
            
            self.conn.commit()
            
            print(f"\n📊 Resumen Categorías:")
            print(f"   ✓ Insertadas: {insertadas}")
            print(f"   - Duplicadas: {duplicadas}")
            print(f"   ✗ Errores: {errores}\n")
            
            return insertadas
            
        except Exception as e:
            print(f"❌ Error al leer el archivo: {str(e)}\n")
            return 0
    
    def importar_clientes(self, archivo_csv='CLIENTES.csv'):
        """
        Importa clientes desde CSV
        
        Formato esperado:
        nombre_comercial,razon_social,tipo,rfc,direccion,contacto,telefono,email
        Hotel Fiesta,Operadora Hotelera SA,Hotel,OPH123456,Calle 60,Juan Pérez,9991234567,contacto@hotel.com
        
        Args:
            archivo_csv: Ruta al archivo CSV
        
        Returns:
            Número de clientes importados
        """
        if not os.path.exists(archivo_csv):
            print(f"⚠️  Archivo '{archivo_csv}' no encontrado. Saltando...")
            return 0
        
        print(f"📂 Importando clientes desde '{archivo_csv}'...")
        
        insertados = 0
        duplicados = 0
        errores = 0
        
        try:
            with open(archivo_csv, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                for i, row in enumerate(reader, start=2):
                    try:
                        nombre_comercial = row.get('nombre_comercial', '').strip()
                        razon_social = row.get('razon_social', '').strip()
                        tipo = row.get('tipo', '').strip()
                        rfc = row.get('rfc', '').strip().upper()
                        direccion = row.get('direccion', '').strip()
                        contacto = row.get('contacto', '').strip()
                        telefono = row.get('telefono', '').strip()
                        email = row.get('email', '').strip()
                        
                        # Validaciones
                        if not nombre_comercial:
                            print(f"   ⚠️  Línea {i}: Nombre comercial vacío, saltando...")
                            continue
                        
                        if tipo not in ['Gobierno', 'Hotel']:
                            print(f"   ⚠️  Línea {i}: Tipo '{tipo}' inválido (debe ser 'Gobierno' o 'Hotel'), saltando...")
                            continue
                        
                        self.cursor.execute("""
                            INSERT INTO clientes 
                            (nombre_comercial, razon_social, tipo, rfc, direccion, contacto, telefono, email)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (nombre_comercial, razon_social, tipo, rfc, direccion, contacto, telefono, email))
                        
                        insertados += 1
                        print(f"   ✓ {nombre_comercial} ({tipo})")
                        
                    except sqlite3.IntegrityError:
                        duplicados += 1
                        print(f"   - {nombre_comercial} (ya existe)")
                    except Exception as e:
                        errores += 1
                        print(f"   ✗ Línea {i}: Error - {str(e)}")
            
            self.conn.commit()
            
            print(f"\n📊 Resumen Clientes:")
            print(f"   ✓ Insertados: {insertados}")
            print(f"   - Duplicados: {duplicados}")
            print(f"   ✗ Errores: {errores}\n")
            
            return insertados
            
        except Exception as e:
            print(f"❌ Error al leer el archivo: {str(e)}\n")
            return 0
    
    def importar_productos(self, archivo_csv='PRODUCTOS.csv'):
        """
        Importa productos desde CSV
        
        Formato esperado:
        ID,CODIGO,DESCRIPCION,CATEGORIA,SUBCATEGORIA,UNIDAD,COSTO,IVA,PRECIO,STOCK,STOCK MIN
        1,CAF001,Café Nescafé Frasco 200g,Café,Café Soluble,Pieza,85.50,SI,120.00,100,20
        
        Notas:
        - ID: Se ignora, el sistema genera su propio ID automáticamente
        - CODIGO: Debe ser único
        - DESCRIPCION: Nombre/descripción del producto
        - IVA: SI/NO, S/N, 1/0, TRUE/FALSE
        - COSTO: Tu precio de compra (precio_base)
        - PRECIO: Precio de venta (opcional, se puede calcular automáticamente)
        - Las categorías y subcategorías deben existir previamente
        
        Args:
            archivo_csv: Ruta al archivo CSV
        
        Returns:
            Número de productos importados
        """
        if not os.path.exists(archivo_csv):
            print(f"⚠️  Archivo '{archivo_csv}' no encontrado. Saltando...")
            return 0
        
        print(f"📂 Importando productos desde '{archivo_csv}'...")
        
        # Cargar categorías y subcategorías existentes
        self.cursor.execute("SELECT id, nombre FROM categorias")
        categorias = {nombre.upper(): id for id, nombre in self.cursor.fetchall()}
        
        self.cursor.execute("SELECT id, nombre, categoria_id FROM subcategorias")
        subcategorias = {(nombre.upper(), cat_id): id for id, nombre, cat_id in self.cursor.fetchall()}
        
        insertados = 0
        duplicados = 0
        errores = 0
        
        try:
            with open(archivo_csv, 'r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                for i, row in enumerate(reader, start=2):
                    try:
                        # Leer campos del CSV (soporta ambos formatos: con/sin espacios)
                        codigo = row.get('CODIGO', row.get('codigo', '')).strip().upper()
                        descripcion = row.get('DESCRIPCION', row.get('descripcion', '')).strip()
                        categoria_nombre = row.get('CATEGORIA', row.get('categoria', '')).strip()
                        subcategoria_nombre = row.get('SUBCATEGORIA', row.get('subcategoria', '')).strip()
                        unidad = row.get('UNIDAD', row.get('unidad', row.get('unidad_medida', 'Pieza'))).strip()
                        costo = row.get('COSTO', row.get('costo', row.get('precio_base', '0'))).strip()
                        iva_str = row.get('IVA', row.get('iva', row.get('aplica_iva', 'SI'))).strip().upper()
                        precio_venta = row.get('PRECIO', row.get('precio', row.get('precio_venta', '0'))).strip()
                        stock = row.get('STOCK', row.get('stock', row.get('stock_actual', '0'))).strip()
                        stock_min = row.get('STOCK MIN', row.get('stock_min', row.get('stock_minimo', '0'))).strip()
                        
                        # Validaciones
                        if not codigo:
                            print(f"   ⚠️  Línea {i}: Código vacío, saltando...")
                            continue
                        
                        if not descripcion:
                            print(f"   ⚠️  Línea {i}: Descripción vacía, saltando...")
                            continue
                        
                        # Convertir COSTO (precio_base)
                        try:
                            costo = float(costo.replace(',', '').replace('$', '').strip())
                        except ValueError:
                            print(f"   ⚠️  Línea {i}: Costo inválido '{costo}', saltando...")
                            continue
                        
                        # Convertir IVA
                        aplica_iva = 1 if iva_str in ['SI', 'S', '1', 'TRUE', 'YES', 'SÍ', 'SÍ'] else 0
                        
                        # Convertir PRECIO (precio_venta)
                        try:
                            precio_venta = float(precio_venta.replace(',', '').replace('$', '').strip())
                        except ValueError:
                            precio_venta = 0  # Si no hay precio, se puede calcular después
                        
                        # Convertir STOCK y STOCK MIN
                        try:
                            stock = float(stock.replace(',', ''))
                            stock_min = float(stock_min.replace(',', ''))
                        except ValueError:
                            print(f"   ⚠️  Línea {i}: Stock inválido, usando 0")
                            stock = 0
                            stock_min = 0
                        
                        # Buscar IDs de categoría y subcategoría
                        categoria_id = None
                        subcategoria_id = None
                        
                        if categoria_nombre:
                            categoria_id = categorias.get(categoria_nombre.upper())
                            if not categoria_id:
                                print(f"   ⚠️  Línea {i}: Categoría '{categoria_nombre}' no existe, creándola...")
                                try:
                                    self.cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (categoria_nombre,))
                                    categoria_id = self.cursor.lastrowid
                                    categorias[categoria_nombre.upper()] = categoria_id
                                    print(f"       ✓ Categoría '{categoria_nombre}' creada")
                                except:
                                    print(f"       ✗ No se pudo crear categoría '{categoria_nombre}'")
                        
                        if subcategoria_nombre and categoria_id:
                            subcategoria_id = subcategorias.get((subcategoria_nombre.upper(), categoria_id))
                            if not subcategoria_id:
                                print(f"   ⚠️  Línea {i}: Subcategoría '{subcategoria_nombre}' no existe, creándola...")
                                try:
                                    self.cursor.execute(
                                        "INSERT INTO subcategorias (categoria_id, nombre) VALUES (?, ?)",
                                        (categoria_id, subcategoria_nombre)
                                    )
                                    subcategoria_id = self.cursor.lastrowid
                                    subcategorias[(subcategoria_nombre.upper(), categoria_id)] = subcategoria_id
                                    print(f"       ✓ Subcategoría '{subcategoria_nombre}' creada")
                                except:
                                    print(f"       ✗ No se pudo crear subcategoría '{subcategoria_nombre}'")
                        
                        # Insertar producto
                        self.cursor.execute("""
                            INSERT INTO productos 
                            (codigo, nombre, descripcion, categoria_id, subcategoria_id, 
                             unidad_medida, precio_base, aplica_iva, precio_venta, stock_actual, stock_minimo)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (codigo, descripcion, '', categoria_id, subcategoria_id,
                              unidad, costo, aplica_iva, precio_venta, stock, stock_min))
                        
                        insertados += 1
                        iva_texto = "con IVA" if aplica_iva else "sin IVA"
                        precio_info = f"Precio venta: ${precio_venta:.2f}" if precio_venta > 0 else "sin precio venta"
                        print(f"   ✓ {codigo} - {descripcion[:40]}... (Costo: ${costo:.2f}, {iva_texto}, {precio_info})")
                        
                    except sqlite3.IntegrityError:
                        duplicados += 1
                        print(f"   - {codigo} (ya existe)")
                    except Exception as e:
                        errores += 1
                        print(f"   ✗ Línea {i}: Error - {str(e)}")
            
            self.conn.commit()
            
            print(f"\n📊 Resumen Productos:")
            print(f"   ✓ Insertados: {insertados}")
            print(f"   - Duplicados: {duplicados}")
            print(f"   ✗ Errores: {errores}\n")
            
            return insertados
            
        except Exception as e:
            print(f"❌ Error al leer el archivo: {str(e)}\n")
            return 0
    
    def crear_plantillas_csv(self):
        """Crea archivos CSV de plantilla con ejemplos"""
        
        print("📝 Creando plantillas CSV de ejemplo...\n")
        
        # Plantilla de categorías
        with open('CATEGORIAS_PLANTILLA.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['nombre'])
            writer.writerow(['Café'])
            writer.writerow(['Equipo de Café'])
            writer.writerow(['Desechables'])
        print("✓ CATEGORIAS_PLANTILLA.csv creado")
        
        # Plantilla de clientes
        with open('CLIENTES_PLANTILLA.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['nombre_comercial', 'razon_social', 'tipo', 'rfc', 'direccion', 'contacto', 'telefono', 'email'])
            writer.writerow(['Hotel Ejemplo', 'Hotelera Nacional SA', 'Hotel', 'HNA123456ABC', 'Calle 60 #100', 'Juan Pérez', '9991234567', 'contacto@hotel.com'])
            writer.writerow(['Secretaría Ejemplo', 'Dependencia de Gobierno', 'Gobierno', 'DEP123456DEF', 'Calle 62 #200', 'María González', '9999876543', 'compras@gob.mx'])
        print("✓ CLIENTES_PLANTILLA.csv creado")
        
        # Plantilla de productos
        with open('PRODUCTOS_PLANTILLA.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'CODIGO', 'DESCRIPCION', 'CATEGORIA', 'SUBCATEGORIA', 'UNIDAD', 'COSTO', 'IVA', 'PRECIO', 'STOCK', 'STOCK MIN'])
            writer.writerow(['', 'CAF001', 'Café Nescafé Clásico Frasco 200g', 'Café', 'Café Soluble', 'Pieza', '85.50', 'SI', '120.00', '100', '20'])
            writer.writerow(['', 'VAS001', 'Vasos Térmicos 8oz Paquete x50', 'Desechables', 'Vasos', 'Paquete', '45.00', 'SI', '63.00', '80', '15'])
            writer.writerow(['', 'EQP001', 'Cafetera Oster 12 Tazas Programable', 'Equipo de Café', 'Cafeteras', 'Pieza', '450.00', 'SI', '630.00', '5', '2'])
        print("✓ PRODUCTOS_PLANTILLA.csv creado")
        
        print("\n✅ Plantillas creadas exitosamente!")
        print("   Edita estos archivos con tus datos y luego impórtalos.\n")
    
    def importar_todo(self):
        """Importa todos los archivos CSV disponibles en orden correcto"""
        
        print("="*70)
        print(" IMPORTACIÓN MASIVA DE DATOS")
        print("="*70)
        print()
        
        total = 0
        
        # 1. Categorías (primero, porque productos las necesitan)
        total += self.importar_categorias()
        
        # 2. Clientes
        total += self.importar_clientes()
        
        # 3. Productos (al final, porque necesitan categorías)
        total += self.importar_productos()
        
        print("="*70)
        print(f"✅ IMPORTACIÓN COMPLETADA - {total} registros insertados")
        print("="*70)
        print()
    
    def cerrar(self):
        """Cierra la conexión a la base de datos"""
        if hasattr(self, 'conn'):
            self.conn.close()
            print("✓ Conexión a la base de datos cerrada\n")

def menu_principal():
    """Menú principal del importador"""
    
    print("="*70)
    print(" IMPORTADOR DE DATOS CSV")
    print(" Sistema de Gestión Comercial - CLF Yucateca")
    print("="*70)
    print()
    
    importador = ImportadorCSV()
    if not importador:
        input("Presiona Enter para salir...")
        return
    
    while True:
        print("\n" + "="*70)
        print(" MENÚ PRINCIPAL")
        print("="*70)
        print()
        print("1. Crear plantillas CSV de ejemplo")
        print("2. Importar CATEGORIAS.csv")
        print("3. Importar CLIENTES.csv")
        print("4. Importar PRODUCTOS.csv")
        print("5. Importar TODO (categorías → clientes → productos)")
        print("6. Salir")
        print()
        
        opcion = input("Selecciona una opción (1-6): ").strip()
        print()
        
        if opcion == '1':
            importador.crear_plantillas_csv()
        elif opcion == '2':
            importador.importar_categorias()
        elif opcion == '3':
            importador.importar_clientes()
        elif opcion == '4':
            importador.importar_productos()
        elif opcion == '5':
            importador.importar_todo()
        elif opcion == '6':
            print("👋 ¡Hasta luego!")
            importador.cerrar()
            break
        else:
            print("⚠️  Opción inválida. Intenta de nuevo.")
        
        if opcion in ['2', '3', '4', '5']:
            input("\nPresiona Enter para continuar...")

if __name__ == '__main__':
    menu_principal()
