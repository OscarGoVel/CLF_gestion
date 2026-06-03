# CLF Sistema de Gestión — Requerimientos Técnicos y Lógica de Base de Datos

> **RFC de la empresa:** CLF240418U94  
> **Versión del documento:** 1.0  
> **Fecha:** 2026-05-05  
> **Propósito:** Referencia técnica para desarrollo, onboarding de IA y auditorías. Este archivo describe el negocio, la arquitectura, el esquema de datos y las reglas de negocio que gobiernan el sistema.

---

## 1. Contexto del Negocio

CLF es una empresa **distribuidora/comercializadora B2B** (business-to-business) en México. Compra productos a proveedores y los revende a clientes corporativos, emitiendo y recibiendo facturas electrónicas CFDI según la normativa del SAT.

### Flujo operativo principal

```
Cliente solicita → Cotización → (cliente autoriza) → Compra a proveedor
→ Entrega al cliente → Facturación → Cobro
```

El sistema gestiona este ciclo completo: catálogos, cotizaciones, compras, inventario, facturas CFDI y análisis financiero.

---

## 2. Arquitectura del Sistema

### Tecnología

| Capa | Tecnología |
|---|---|
| Backend web | Python 3.13 + FastAPI |
| Plantillas HTML | Jinja2 + HTMX (interactividad sin JS pesado) |
| CSS | Tailwind CSS |
| Base de datos | PostgreSQL (migrado desde SQLite) |
| Autenticación | JWT (HS256, TTL 8 horas) + PBKDF2-HMAC-SHA256 |
| App de escritorio (legacy) | Python + Tkinter |
| Generación de PDF | Librería PDF personalizada |
| Servidor web | Uvicorn / Nginx (reverse proxy) |

### Bases de datos

El sistema usa **dos bases de datos separadas en PostgreSQL**:

- `clf_usuarios` — usuarios globales y preferencias (compartida entre todas las empresas)
- `clf_empresa` (o el nombre configurado por empresa) — datos operativos de cada empresa

Esto permite arquitectura **multi-empresa**: una instalación puede gestionar más de una razón social.

### Módulos / Routers

| Router | Prefijo URL | Función |
|---|---|---|
| `catalogos` | `/catalogos` | Clientes, proveedores, productos |
| `cotizaciones` | `/cotizaciones` | Ciclo de ventas completo |
| `compras` | `/compras` | Registro de compras a proveedores |
| `facturas` | `/facturas` | Importación y vinculación de CFDI |
| `stock` | `/stock` | Inventario y movimientos |
| `preinventario` | `/preinventario` | Conteo físico de inventario |
| `estudio_mercado` | `/estudio-mercado` | Estudio de precios de mercado |
| `estado_cuenta` | `/estado-cuenta` | Estado de cuenta por cliente |
| `analisis` | `/analisis` | Análisis de costos y métricas |
| `admin` | `/admin` | Usuarios, permisos, ubicaciones |
| `herramientas` | `/herramientas` | CFDI, vinculación, utilidades |
| `cfdi` | `/cfdi` | Importación masiva de XMLs |

---

## 3. Esquema de Base de Datos

### 3.1 Base: `clf_usuarios` (global)

```sql
usuarios (
    id             SERIAL PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    nombre         TEXT NOT NULL,
    password_hash  TEXT NOT NULL,   -- PBKDF2-HMAC-SHA256, 200,000 iteraciones
    salt           TEXT,            -- salt aleatorio por usuario (hex 32 bytes)
    rol            TEXT NOT NULL DEFAULT 'Operador',
    activo         INTEGER DEFAULT 1,
    fecha_creacion TIMESTAMPTZ DEFAULT NOW(),
    ultimo_acceso  TIMESTAMPTZ
)

preferencias_usuario (
    usuario_id INTEGER NOT NULL,
    clave      TEXT NOT NULL,
    valor      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (usuario_id, clave)
)
```

### 3.2 Base: `clf_empresa` (por empresa)

#### Catálogos

```sql
clientes (
    id               SERIAL PRIMARY KEY,
    nombre_comercial TEXT NOT NULL,
    razon_social     TEXT,
    tipo             TEXT NOT NULL,       -- 'Empresa', 'Gobierno', 'Persona física', etc.
    rfc              TEXT,
    direccion        TEXT,
    contacto         TEXT,
    telefono         TEXT,
    email            TEXT,
    regimen_fiscal   TEXT,                -- para timbrado CFDI
    uso_cfdi         TEXT,
    cp_fiscal        TEXT,
    corporativo_id   INTEGER,             -- FK a corporativos (grupo empresarial)
    activo           BOOLEAN DEFAULT TRUE,
    fecha_registro   TIMESTAMPTZ DEFAULT NOW()
)

corporativos (
    id     SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE           -- agrupa clientes del mismo grupo empresarial
)

proveedores (
    id             SERIAL PRIMARY KEY,
    nombre         TEXT NOT NULL,
    razon_social   TEXT,
    rfc            TEXT,
    direccion      TEXT,
    contacto       TEXT,
    telefono       TEXT,
    email          TEXT,
    notas          TEXT,
    regimen_fiscal TEXT,
    cp_fiscal      TEXT,
    uso_cfdi       TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT NOW()
)

categorias (
    id     SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
)

subcategorias (
    id           SERIAL PRIMARY KEY,
    categoria_id INTEGER REFERENCES categorias(id),
    nombre       TEXT NOT NULL
)

metodos_pago (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT UNIQUE NOT NULL,    -- Efectivo, Transferencia, Tarjeta, etc.
    descripcion TEXT,
    activo      INTEGER DEFAULT 1
)
```

#### Productos e inventario

```sql
productos (
    id                SERIAL PRIMARY KEY,
    codigo            TEXT UNIQUE NOT NULL,
    nombre            TEXT NOT NULL,
    descripcion       TEXT,
    categoria_id      INTEGER REFERENCES categorias(id),
    subcategoria_id   INTEGER REFERENCES subcategorias(id),
    unidad_medida     TEXT,
    precio_base       NUMERIC(14,4) NOT NULL,   -- precio sin IVA
    aplica_iva        INTEGER DEFAULT 1,
    precio_venta      NUMERIC(14,4),            -- precio con margen aplicado
    stock_actual      NUMERIC(14,4) DEFAULT 0,
    stock_minimo      NUMERIC(14,4) DEFAULT 0,
    clave_sat         TEXT,                     -- clave producto/servicio SAT (CFDI)
    clave_unidad_sat  TEXT,                     -- clave unidad SAT
    precio_base_fecha TEXT,                     -- fecha de la última actualización de precio_base
    costo_promedio    NUMERIC(14,4),            -- calculado a partir de compras (costo promedio ponderado)
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
)

producto_proveedor (
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    proveedor_id   INTEGER NOT NULL REFERENCES proveedores(id),
    es_principal   INTEGER DEFAULT 0,           -- 1 = proveedor preferido
    notas          TEXT,
    UNIQUE(producto_id, proveedor_id)
)

producto_claves_sat (
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    clave_sat      TEXT NOT NULL,
    fuente         TEXT DEFAULT 'xml_import',   -- origen: manual o importado de CFDI
    UNIQUE(producto_id, clave_sat)
)

producto_precio_historial (
    id          SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id),
    proveedor_id INTEGER REFERENCES proveedores(id),
    precio      NUMERIC(14,4) NOT NULL,
    fecha       TEXT NOT NULL,
    motivo      TEXT,
    fuente      TEXT DEFAULT 'manual'
)

movimientos_stock (
    id            SERIAL PRIMARY KEY,
    producto_id   INTEGER NOT NULL REFERENCES productos(id),
    tipo          TEXT NOT NULL,            -- 'entrada' | 'salida' | 'ajuste'
    motivo        TEXT,                     -- Merma/Daño, Uso interno, etc.
    cantidad      NUMERIC(14,4) NOT NULL,
    stock_antes   NUMERIC(14,4) NOT NULL,
    stock_despues NUMERIC(14,4) NOT NULL,
    referencia    TEXT,                     -- folio de compra, cotización, etc.
    notas         TEXT,
    usuario       TEXT,
    fecha         TIMESTAMPTZ DEFAULT NOW()
)
```

#### Cotizaciones (flujo de ventas)

```sql
cotizaciones (
    id                SERIAL PRIMARY KEY,
    folio             TEXT UNIQUE NOT NULL,     -- formato: COT-YYYY-NNNN
    fecha             DATE NOT NULL,
    cliente_id        INTEGER NOT NULL REFERENCES clientes(id),
    subtotal          NUMERIC(14,4) DEFAULT 0,
    iva               NUMERIC(14,4) DEFAULT 0,
    total             NUMERIC(14,4) DEFAULT 0,
    aplica_iva        INTEGER DEFAULT 0,
    notas             TEXT,
    observaciones     TEXT,
    estado            TEXT DEFAULT 'Pendiente', -- ver máquina de estados
    orden_compra      TEXT,
    fecha_orden_compra DATE,
    fecha_entrega     DATE,
    fecha_factura     DATE,
    fecha_pago        DATE,
    monto_entregado   NUMERIC(14,4) DEFAULT 0,
    monto_facturado   NUMERIC(14,4) DEFAULT 0,
    monto_pagado      NUMERIC(14,4) DEFAULT 0,
    numero_factura    TEXT,
    entrega_parcial   INTEGER DEFAULT 0,        -- 1 = tiene entregas parciales
    oc_documento      TEXT,                     -- ruta al PDF de la OC
    factura_documento TEXT,
    utilidad_pct      NUMERIC(6,2) DEFAULT 0,   -- margen de utilidad calculado
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
)

cotizacion_detalle (
    id              SERIAL PRIMARY KEY,
    cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id),
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        NUMERIC(14,4) NOT NULL,
    precio_unitario NUMERIC(14,4) NOT NULL,
    subtotal        NUMERIC(14,4) NOT NULL,
    iva             NUMERIC(14,4) DEFAULT 0,
    total           NUMERIC(14,4) NOT NULL,
    costo_snapshot  NUMERIC(14,4),              -- costo al momento de crear la cotización
    tiene_stock     INTEGER DEFAULT 1           -- 1 = hay stock para cubrir esta línea
)

seguimiento_etapas (
    id            SERIAL PRIMARY KEY,
    cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id),
    etapa         TEXT NOT NULL,
    completada    INTEGER DEFAULT 0,
    referencia    TEXT,
    fecha_etapa   DATE,
    notas         TEXT,
    UNIQUE(cotizacion_id, etapa)
)

entregas_parciales (
    id                 SERIAL PRIMARY KEY,
    cotizacion_id      INTEGER NOT NULL REFERENCES cotizaciones(id),
    producto_id        INTEGER NOT NULL REFERENCES productos(id),
    cantidad_entregada NUMERIC(14,4) NOT NULL,
    fecha_entrega      DATE NOT NULL,
    notas              TEXT,
    usuario            TEXT
)

documentos_cotizacion (
    id             SERIAL PRIMARY KEY,
    cotizacion_id  INTEGER NOT NULL REFERENCES cotizaciones(id),
    tipo           TEXT NOT NULL,               -- 'orden_compra', 'factura', 'remision', etc.
    nombre_archivo TEXT NOT NULL,
    ruta_archivo   TEXT NOT NULL,
    notas          TEXT
)
```

#### Compras

```sql
compras (
    id                SERIAL PRIMARY KEY,
    folio             TEXT UNIQUE NOT NULL,     -- formato: CMP-YYYY-NNNN
    proveedor_id      INTEGER REFERENCES proveedores(id),
    fecha_compra      TIMESTAMPTZ NOT NULL,
    subtotal          NUMERIC(14,4) DEFAULT 0,
    iva               NUMERIC(14,4) DEFAULT 0,
    total             NUMERIC(14,4) DEFAULT 0,
    metodo_pago_id    INTEGER REFERENCES metodos_pago(id),
    notas             TEXT,
    ticket_referencia TEXT,
    cotizacion_id     INTEGER,                  -- cotización principal vinculada (opcional)
    factura_xml_id    INTEGER,                  -- ID de la factura CFDI asociada (opcional)
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
)

compra_detalle (
    id             SERIAL PRIMARY KEY,
    compra_id      INTEGER NOT NULL REFERENCES compras(id),
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    cantidad       NUMERIC(14,4) NOT NULL,
    costo_unitario NUMERIC(14,4) NOT NULL,
    costo_total    NUMERIC(14,4) NOT NULL
)

compra_detalle_cotizacion (
    id                SERIAL PRIMARY KEY,
    compra_detalle_id INTEGER NOT NULL REFERENCES compra_detalle(id),
    cotizacion_id     INTEGER REFERENCES cotizaciones(id),
    cantidad          NUMERIC(14,4) NOT NULL,   -- cuántas unidades de esta compra se asignan a esa cotización
    notas             TEXT
)
```

#### Facturas CFDI

```sql
facturas (
    id               SERIAL PRIMARY KEY,
    uuid             TEXT UNIQUE NOT NULL,      -- UUID del timbre SAT
    serie            TEXT,
    folio_factura    TEXT,
    fecha            TEXT,
    fecha_timbrado   TEXT,
    no_cert_sat      TEXT,
    rfc_emisor       TEXT,
    nombre_emisor    TEXT,
    rfc_receptor     TEXT,
    nombre_receptor  TEXT,
    uso_cfdi         TEXT,
    tipo             TEXT,                      -- 'venta' (CLF emite) | 'compra' (CLF recibe)
    metodo_pago      TEXT,                      -- PUE, PPD
    forma_pago       TEXT,                      -- 01 efectivo, 03 transferencia, etc.
    moneda           TEXT DEFAULT 'MXN',
    subtotal         NUMERIC(14,4) DEFAULT 0,
    descuento        NUMERIC(14,4) DEFAULT 0,
    iva              NUMERIC(14,4) DEFAULT 0,
    total            NUMERIC(14,4) DEFAULT 0,
    ruta_xml         TEXT,                      -- ruta al archivo XML original
    notas            TEXT,
    fecha_registro   TIMESTAMPTZ DEFAULT NOW()
)

factura_conceptos (
    id                SERIAL PRIMARY KEY,
    factura_id        INTEGER NOT NULL REFERENCES facturas(id),
    clave_prod_serv   TEXT,                     -- clave SAT del producto/servicio
    no_identificacion TEXT,                     -- código interno del producto
    cantidad          NUMERIC(14,4),
    clave_unidad      TEXT,
    unidad            TEXT,
    descripcion       TEXT,
    valor_unitario    NUMERIC(14,4),
    importe           NUMERIC(14,4),
    descuento         NUMERIC(14,4) DEFAULT 0
)
```

#### Tablas relacionales y auxiliares

```sql
factura_cotizaciones (
    factura_id    INTEGER NOT NULL REFERENCES facturas(id),
    cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id),
    fecha_vinculo TIMESTAMPTZ DEFAULT NOW(),
    notas         TEXT,
    UNIQUE(factura_id, cotizacion_id)
)

ordenes_compra (
    id          SERIAL PRIMARY KEY,
    numero      TEXT,
    cliente_id  INTEGER REFERENCES clientes(id),
    fecha       TEXT,
    monto_total NUMERIC(14,4) DEFAULT 0,
    documento   TEXT,                           -- ruta al archivo PDF/imagen
    notas       TEXT
)

oc_cotizaciones (
    oc_id         INTEGER NOT NULL REFERENCES ordenes_compra(id),
    cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id),
    UNIQUE(oc_id, cotizacion_id)
)

config_permisos (
    permiso_key TEXT NOT NULL,
    rol         TEXT NOT NULL,
    PRIMARY KEY (permiso_key, rol)
)
```

---

## 4. Reglas de Negocio Críticas

### 4.1 Máquina de Estados de Cotización

Una cotización sigue esta cadena de estados (la dirección es siempre hacia adelante, salvo cancelar):

```
Pendiente → Programada → Parcialmente Entregada → Entregada → Facturada → Pagada
                                                                         ↗
              Cualquier estado (excepto Pagada) ────────────────→ Cancelada
```

| Estado | Significado operativo |
|---|---|
| **Pendiente** | Cotización enviada al cliente, esperando autorización |
| **Programada** | Cliente autorizó el pedido (orden de compra recibida) |
| **Parcialmente Entregada** | Se entregaron algunos productos, faltan otros |
| **Entregada** | Todos los productos fueron entregados al cliente |
| **Facturada** | Se emitió el CFDI de venta |
| **Pagada** | El cliente liquidó el saldo total |
| **Cancelada** | La cotización fue cancelada |

**Estados de venta confirmada** (cliente autorizó): Programada, Parcialmente Entregada, Entregada, Facturada, Pagada.

**Estados con saldo pendiente de cobro**: Programada, Parcialmente Entregada, Entregada, Facturada.

### 4.2 Generación de Folios

- **Cotización:** `COT-YYYY-NNNN` — se genera con `pg_advisory_xact_lock` para evitar duplicados en acceso concurrente.
- **Compra:** `CMP-YYYY-NNNN` — generado secuencialmente por año.
- Los folios son únicos dentro del año calendario.

### 4.3 Cálculo de Costo al Entregar

Cuando una cotización se marca como **Entregada**, el sistema calcula el costo real de cada línea con esta prioridad:

1. **Compra directa asignada** — promedio ponderado de `compra_detalle_cotizacion` para ese producto y cotización.
2. **Costo promedio del producto** — `productos.costo_promedio` si es mayor a 0.
3. **Snapshot del catálogo** — `cotizacion_detalle.costo_snapshot` (el costo al momento de crear la cotización).

Este mecanismo garantiza que el margen de utilidad calculado refleje el costo real de adquisición.

### 4.4 Clasificación ABC de Inventario

El módulo de stock clasifica automáticamente los productos por valor de inventario (`stock_actual × costo_promedio`):

| Categoría | Criterio | Significado |
|---|---|---|
| **A** | Primeros productos que acumulan el 80% del valor total | Alta importancia, control estricto |
| **B** | Siguiente tramo hasta el 95% acumulado | Importancia media |
| **C** | El restante 5% | Baja rotación o bajo valor |

### 4.5 Vinculación CFDI

El sistema detecta automáticamente **pendientes de vinculación** al importar facturas XML:

- **Clientes sin registrar** — RFC receptor de facturas de venta no existe en el catálogo.
- **Proveedores sin registrar** — RFC emisor de facturas de compra no existe en el catálogo.
- **Productos sin vincular** — `no_identificacion` o `clave_prod_serv` en conceptos no corresponde a ningún producto.
- **Facturas de venta sin cotización** — CLF emitió la factura pero no tiene cotización vinculada.
- **Facturas de compra sin registro** — CLF recibió la factura pero no hay compra registrada.

El RFC propio `CLF240418U94` se excluye del análisis de clientes y proveedores para evitar falsos positivos.

### 4.6 Movimientos de Stock

Cada cambio en inventario genera un registro en `movimientos_stock` con:
- Stock antes y después (inmutable, para auditoría)
- Tipo: `entrada` | `salida` | `ajuste`
- Referencia al folio de compra o cotización que originó el movimiento
- Usuario que realizó la acción

Los motivos de salida disponibles son: Merma/Daño, Uso interno, Devolución a proveedor, Ajuste de inventario, Muestra/Demo, Pérdida, Otro.

---

## 5. Control de Acceso (RBAC)

### Jerarquía de roles

| Rol | Nivel | Descripción |
|---|---|---|
| **Administrador** | 3 | Acceso total, incluyendo configuración del sistema |
| **Operador** | 2 | Operaciones comerciales: cotizar, comprar, facturar |
| **Almacenista** | 2 | Enfocado en stock y pre-inventario |
| **Solo lectura** | 1 | Solo consulta, sin modificaciones |

### Permisos configurables por empresa

Los permisos por defecto pueden sobreescribirse por empresa en la tabla `config_permisos`. Los permisos incluyen:

| Clave | Acción |
|---|---|
| `cotizacion.crear` | Crear nueva cotización |
| `cotizacion.editar` | Editar cotización existente |
| `cotizacion.cambiar_estado` | Avanzar el estado de una cotización |
| `cotizacion.marcar_pagada` | Solo Administrador por defecto |
| `cotizacion.ver_precios` | Ver montos e importes |
| `factura.importar` | Importar XML del SAT |
| `factura.vincular` | Vincular factura a cotización |
| `stock.entrada_manual` | Registrar entrada de inventario |
| `stock.salida_manual` | Registrar salida de inventario |
| `catalogo.crear_editar` | Crear/editar clientes, proveedores, productos |
| `catalogo.eliminar` | Eliminar registros del catálogo |
| `preinventario.capturar` | Capturar conteo físico |
| `preinventario.aprobar` | Aprobar o rechazar sesión de conteo |
| `estudio.gestionar` | Crear y capturar estudios de mercado |
| `estudio.aplicar_catalogo` | Actualizar precio de catálogo desde el estudio |

> El rol **Administrador** siempre tiene todos los permisos, sin excepción.

### Autenticación

- **Hash de contraseña:** PBKDF2-HMAC-SHA256 con 200,000 iteraciones y salt aleatorio por usuario (32 bytes hex).
- **Sesión:** JWT firmado con HS256, TTL de 8 horas.
- **Migración legacy:** El sistema detecta hashes con salt estático (esquema antiguo) y los acepta para compatibilidad durante la migración.

---

## 6. Índices de Rendimiento

```sql
-- Cotizaciones: filtrado por estado, fecha y cliente
idx_cot_estado        ON cotizaciones(estado)
idx_cot_fecha         ON cotizaciones(fecha)
idx_cot_fecha_entrega ON cotizaciones(fecha_entrega)
idx_cot_cliente       ON cotizaciones(cliente_id)

-- Facturas: búsqueda por UUID y RFC
idx_fac_uuid          ON facturas(uuid)
idx_fac_rfc_emisor    ON facturas(rfc_emisor)
idx_fac_rfc_receptor  ON facturas(rfc_receptor)

-- Productos: búsqueda por código
idx_prod_codigo       ON productos(codigo)

-- Detalle y movimientos: join por foreign key
idx_cotdet_cotizacion ON cotizacion_detalle(cotizacion_id)
idx_facdet_factura    ON factura_conceptos(factura_id)
idx_mov_producto      ON movimientos_stock(producto_id)
idx_mov_fecha         ON movimientos_stock(fecha)
```

---

## 7. Configuración del Sistema

El archivo `config.json` (no versionado) contiene:

```json
{
  "postgresql": {
    "host": "...",
    "port": 5432,
    "user": "...",
    "password": "...",
    "database_usuarios": "clf_usuarios"
  },
  "empresas": [
    {
      "nombre": "CLF",
      "pg_database": "clf_empresa",
      "rfc": "CLF240418U94"
    }
  ],
  "preferencias": {
    "empresa_key": {
      "pdf": {
        "vigencia": "30 DÍAS",
        "lugar_entrega": "MÉRIDA",
        "tiempo_entrega": "...",
        "moneda": "...",
        "cambios": "..."
      }
    }
  }
}
```

---

## 8. Generación de PDFs

El sistema genera PDFs para:

| Documento | Módulo |
|---|---|
| Cotización | `pdf_cotizacion.py` |
| Estado de cuenta por cliente | `pdf_estado_cuenta.py` |
| Presupuesto de compra | `pdf_presupuesto_compra.py` |

Los PDFs incluyen logo de la empresa, condiciones de venta (vigencia, lugar de entrega, tiempo de entrega, condiciones de precio) y se personalizan desde `PDF_CONFIG`.

---

## 9. Módulos Especiales

### Pre-inventario
Flujo de conteo físico supervisado:
1. Almacenista captura conteos por ubicación.
2. Administrador aprueba o rechaza la sesión.
3. Al aprobar, `stock_actual` de los productos se actualiza con los conteos.

### Estudio de Mercado
Permite capturar precios de mercado de proveedores para un producto y decidir si actualizar el precio base del catálogo. Requiere permiso `estudio.aplicar_catalogo` para modificar precios.

### Estado de Cuenta
Vista consolidada de todas las cotizaciones de un cliente con saldo pendiente, mostrando montos entregados, facturados y pagados, y la diferencia por cobrar.

### Análisis de Costos
Módulo de reportes con métricas de utilidad, rotación de inventario y comparativo de ventas por período.

---

## 10. Consideraciones para Desarrollo Futuro

- **Multi-empresa:** La arquitectura ya soporta múltiples bases de datos. Para agregar una empresa nueva se necesita crear la base de datos PostgreSQL, ejecutar `migrate_schema.py` y registrar la empresa en `config.json`.
- **Costo promedio ponderado:** El campo `productos.costo_promedio` se actualiza al registrar compras. La lógica de actualización debe garantizar atomicidad con el movimiento de stock.
- **Auditoría:** Existe un módulo `audit.py` que registra acciones sensibles. Las tablas de auditoría no están en este esquema porque se gestionan por separado.
- **Seguridad del JWT:** El `SECRET_KEY` para firmar tokens se configura en variables de entorno o en `web_app/config.py`. No debe estar hardcodeado en código.
- **Backups:** La base `clf_usuarios` es crítica; su pérdida bloquea el acceso a todas las empresas. Debe tener respaldo independiente.
