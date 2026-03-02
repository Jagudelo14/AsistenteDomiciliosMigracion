# Asistente WhatsApp Domicilios (Sierra Nevada)

Asistente conversacional para atencion por WhatsApp: toma pedidos, gestiona direccion y cobertura, calcula tiempos, define metodo de entrega/pago y escala casos a un administrador cuando aplica.

## Objetivo

Este proyecto implementa un agente para restaurante que:

- Atiende mensajes entrantes de WhatsApp (texto, audio, ubicacion e imagen).
- Detecta intencion del cliente con OpenAI.
- Orquesta subflujos de negocio (pedido, direccion, pago, quejas, etc.).
- Persiste estado y contexto en PostgreSQL para mantener continuidad.
- Responde por WhatsApp Cloud API.

## Flujo general del sistema

1. **Webhook**
- Endpoint principal: `/wpp`.
- `GET`: verificacion del webhook de Meta.
- `POST`: procesamiento de mensajes entrantes.

2. **Recepcion y normalizacion**
- Texto: se procesa directo.
- Audio: se transcribe con Whisper.
- Ubicacion: se usa para cobertura/sede y direccion.
- Imagen: se interpreta como posible soporte de pago.

3. **Control de idempotencia**
- Se valida `message_id` para evitar reprocesar mensajes duplicados.

4. **Onboarding del cliente**
- Si es cliente nuevo, se crea registro en `clientes_whatsapp`.
- Se solicita nombre y direccion para habilitar flujo completo.

5. **Contexto + clasificacion**
- Se recupera contexto reciente de conversacion.
- Se clasifica intencion y tipo de mensaje con OpenAI.

6. **Orquestacion de subflujos**
- Segun la intencion, se ejecuta el subflujo correspondiente:
  - solicitud/modificacion/confirmacion de pedido
  - domicilio o recogida en sede
  - confirmacion de direccion
  - medio de pago y verificacion
  - preguntas generales, promociones, quejas, transferencia

7. **Persistencia y cierre**
- Se guardan pedidos en `pedidos` y `detalle_pedido`.
- Se guarda intencion futura para continuidad.
- Se confirma pedido y se notifica a administracion cuando aplica.

## Arquitectura (modulos principales)

- `function_app.py`: entrypoint HTTP (Azure Functions), webhook y ruteo inicial.
- `utils_subflujos.py`: motor de decisiones y subflujos de negocio.
- `utils_chatgpt.py`: clasificacion, extraccion y generacion de mensajes con OpenAI.
- `utils_contexto.py`: persistencia/lectura de contexto conversacional.
- `utils_google.py`: geocodificacion, cobertura, sede, tiempos de envio.
- `utils_pagos.py`: integracion de pagos y verificacion.
- `utils.py`: utilidades de negocio/DB/WhatsApp/logs.
- `utils_database.py`: conexion y ejecucion de consultas PostgreSQL.
- `utils_registration.py`: banderas de onboarding y datos personales.
- `Tablas.sql`: esquema de base de datos.

## Contexto, memoria y continuidad

La continuidad se apoya en 3 capas:

1. **Conversacion corta**
- Tabla `conversaciones` (JSONB con mensajes y roles).
- Sirve para interpretar respuestas breves y contexto inmediato.

2. **Estado conversacional**
- Tabla `clasificacion_intenciones_futuras`.
- Define "en que paso va" el cliente (ej: `confirmar_direccion`, `medio_pago`).

3. **Estado de negocio**
- Tablas `clientes_whatsapp`, `pedidos`, `detalle_pedido`.
- Guarda datos durables de cliente, pedido y operacion.

## Es buena idea tener resumen del cliente y estado?

**Si, es una muy buena idea y en este tipo de agente es clave.**

### Por que

- Evita perder el hilo cuando el cliente responde con "si", "no", "listo", "ya".
- Reduce errores en pasos criticos (confirmacion direccion, pago, entrega).
- Permite retomar conversaciones despues de pausas o mensajes fuera de orden.
- Facilita handoff a humano con contexto util.

### Recomendacion practica

Mantener dos objetos persistentes por telefono:

1. **Resumen del cliente (snapshot corto)**
- nombre
- direccion_confirmada
- id_sede
- preferencia_entrega (domicilio/recoger)
- ultimo_pedido_codigo
- metodo_pago_preferido
- datos_personales_completos (bool)
- timestamp_ultima_interaccion

2. **Estado conversacional (state machine)**
- `estado_actual`
- `subestado`
- `esperando_campo` (ej: `direccion`, `medio_pago`)
- `codigo_pedido_activo`
- `ultima_pregunta_bot`
- `intento_reintentos`
- `expira_en`

## Flujo completo de pedido (ejemplo)

1. Cliente saluda o pide productos.
2. Clasificacion -> `solicitud_pedido`.
3. Mapeo del pedido al menu y guardado temporal.
4. Bot muestra resumen del pedido y pide confirmacion.
5. Cliente confirma -> se pregunta metodo de entrega.
6. Si domicilio:
- validar/confirmar direccion
- calcular tiempo y costo
- solicitar medio de pago y datos personales
7. Si recoger:
- seleccionar sede
- estimar tiempo de recogida
- confirmar medio de pago
8. Cierre:
- marcar pedido definitivo
- limpiar intencion futura
- notificar a administracion/sede

## Tablas clave de BD

- `clientes_whatsapp`: perfil y datos operativos del cliente.
- `conversaciones`: historial corto para contexto.
- `historico_conversaciones`: trazabilidad de sesiones.
- `clasificacion_intenciones_futuras`: estado de continuidad.
- `pedidos`: cabecera del pedido.
- `detalle_pedido`: items del pedido.
- `items`: menu base.
- `disponibilidad_items`: menu disponible por sede.
- `sedes`, `sedes_areas`: sedes y zonas de cobertura.
- `id_whatsapp_messages`: control de duplicados.
- `quejas`, `quejas_graves`: trazabilidad de escalaciones.
- `logs`: auditoria tecnica y funcional.

## Estructura de base de datos (detalle)

### Mapa de relaciones (resumen)

- `clientes (1) -> (N) sedes` por `sedes.id_restaurante`.
- `clientes (1) -> (N) clientes_whatsapp` por `clientes_whatsapp.id_restaurante`.
- `clientes_whatsapp (1) -> (N) pedidos` por `pedidos.id_whatsapp`.
- `pedidos (1) -> (N) detalle_pedido` por `detalle_pedido.id_pedido`.
- `items (1) -> (N) detalle_pedido` por `detalle_pedido.id_producto`.
- `sedes (1) -> (N) disponibilidad_items` por `disponibilidad_items.id_sede`.
- `items (1) -> (N) disponibilidad_items` por `disponibilidad_items.id_item`.
- `sedes (1) -> (N) sedes_areas` por `sedes_areas.id_sede`.
- `promociones (1) -> (N) disponibilidad_promociones` por `disponibilidad_promociones.id_promocion`.
- `sedes (1) -> (N) disponibilidad_promociones` por `disponibilidad_promociones.id_sede`.

### Tablas operativas y campos importantes

- `clientes_whatsapp`
- PK: `id_whatsapp`.
- Unico: `telefono`.
- Perfil y onboarding: `nombre`, `telefono`, `id_restaurante`, `id_sede`.
- Ubicacion: `direccion_google`, `latitud`, `longitud`, `observaciones_dir`.
- Estado de registro: `dir_primera_vez`, `nombre_bool`, `datos_personales`.
- Facturacion: `Tipo_Doc`, `N_Doc`, `email`.

- `conversaciones`
- PK: `id_conversaciones`.
- Contexto corto: `conversacion` (JSONB), `telefono`, `fecha_mensaje`, `id_cliente`.
- Uso: recuperar ultimos mensajes para clasificacion y continuidad.

- `historico_conversaciones`
- PK: `id`.
- Trazabilidad: `telefono`, `primer_mensaje`, `ultimo_mensaje`, `cantidad_mensajes`, `id_cliente`.

- `clasificacion_intenciones_futuras`
- PK: `telefono`.
- Estado de flujo: `intencion_futura`, `observaciones`.
- Memoria de turno: `mensaje_chatbot`, `mensaje_usuario`.
- Contexto promocional: `datos_promocion` (JSONB).
- Control temporal: `fecha_actualizacion`.

- `pedidos`
- PK: `idpedido`.
- Identidad de pedido: `codigo_unico`, `id_whatsapp`, `idcliente`, `idsede`.
- Estado: `estado`, `es_temporal`, `es_promocion`.
- Totales/logistica: `total_productos`, `total_domicilio`, `total_final`, `distancia`, `tiempo_estimado`.
- Entrega/pago: `metodo_entrega`, `metodo_pago`, `id_pago`, `direccion`.
- Tiempo de creacion: `fecha`, `hora`.

- `detalle_pedido`
- PK: `id_detalle`.
- Relacion pedido-item: `id_pedido`, `id_producto`.
- Contenido: `cantidad`, `total`, `especificaciones`.

- `items`
- PK: `iditem`.
- Catalogo: `nombre`, `precio`, `descripcion`, `tipo_comida`, `observaciones`, `estado`, `idcliente`.

- `disponibilidad_items`
- PK: `id_disponibilidad`.
- Disponibilidad por sede: `id_item`, `id_sede`, `disponible`.

- `sedes`
- PK: `id_sede`.
- Datos sede: `nombre`, `direccion`, `ciudad`, `telefono`, `correo`, `id_restaurante`.
- Geografia y operacion: `latitud`, `longitud`, `estado`, `horarios`, `num_admin`.

- `sedes_areas`
- PK: `id`.
- Cobertura: `id_sede`, `valor` (poligono serializado), `geom` (PostGIS Polygon).
- Reglas: `prioridad`, `costo_domicilio`, `hora_inicio`, `hora_fin`.

- `id_whatsapp_messages`
- Control de idempotencia por mensaje entrante: `id_messages`.

- `quejas` y `quejas_graves`
- Registro de escalaciones: `sender`, `queja_original`, `respuesta_agente`, metadatos de accion/resumen.

- `logs`
- Auditoria tecnica: `ambiente`, `tipo`, `mensaje`, `archivoPy`, `function`, `lineNumber`, `telefono`.

### Indices y restricciones relevantes

- `clientes_whatsapp.telefono` tiene restriccion unica para evitar duplicados de cliente.
- `clasificacion_intenciones_futuras.telefono` como PK permite un estado activo por cliente.
- Indices de rendimiento en tablas de alto trafico:
- `idx_conversaciones_telefono`
- `idx_historico_telefono`
- `idx_pedidos_estado`
- `idx_pedidos_fecha`
- `idx_pedidos_idsede_fecha`
- `idx_pedidos_idcliente_idsede_fecha`
- Indice geoespacial:
- `idx_sedes_areas_geom` (GiST) para consultas de cobertura.

## Variables de entorno (referencia)

Configura al menos:

- `OPENAI_API_KEY`
- `WABA_TOKEN`
- `PHONE_NUMBER_ID`
- `META_VERIFY_TOKEN`
- `ID_RESTAURANTE`
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`
- `API_KEY_GOOGLE_MAPS`
- `NUMERO_ADMIN`

> No publiques secretos en repositorio.

## Ejecucion local

1. Instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Ejecutar prueba local con payload de ejemplo:

```bash
python run_local.py
```

3. O levantar Azure Functions localmente (si usas Core Tools):

```bash
func start
```

## Recomendaciones de robustez

- Usar maquina de estados explicita por conversacion.
- Versionar el resumen de cliente (ej: `resumen_version`).
- Definir expiracion de estado para evitar "sesiones zombie".
- Registrar cada transicion de estado (from -> to -> motivo).
- Mantener idempotencia por mensaje y por evento de pago.
- Tener estrategia de fallback a agente humano cuando el flujo quede ambiguo.

## Nota operativa

El proyecto ya tiene base de continuidad (intencion futura + contexto en BD). El siguiente paso recomendado es formalizarlo como **state machine** con estados y transiciones bien definidos para reducir desalineaciones en confirmacion de direccion, eleccion de sede y pago.
