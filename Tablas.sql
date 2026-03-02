--
-- PostgreSQL database dump
--

\restrict 72PgmdtpzYyCwqKfaDJbv5Bvqwh2O47W0yM6Pw4hNcLrkjd89icLUTe2oYVpeCu

-- Dumped from database version 14.19
-- Dumped by pg_dump version 18.1

-- Started on 2026-02-28 14:15:47

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 6 (class 2615 OID 2200)
-- Name: public; Type: SCHEMA; Schema: -; Owner: azure_pg_admin
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO azure_pg_admin;

--
-- TOC entry 2 (class 3079 OID 54734)
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- TOC entry 5074 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 232 (class 1259 OID 44353)
-- Name: branding; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.branding (
    id_branding integer NOT NULL,
    idcliente integer NOT NULL,
    logo_url text,
    color_primario character varying(10),
    color_texto_sobre_primario character varying(10),
    color_secundario character varying(10),
    color_acento character varying(10),
    color_fondo character varying(10),
    color_texto_principal character varying(10),
    nombre_empresa character varying(150),
    direccion text,
    telefono character varying(50),
    correo_electronico character varying(100),
    subdominio character varying(100)
);


ALTER TABLE public.branding OWNER TO netadmin;

--
-- TOC entry 231 (class 1259 OID 44352)
-- Name: branding_id_branding_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.branding_id_branding_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.branding_id_branding_seq OWNER TO netadmin;

--
-- TOC entry 5150 (class 0 OID 0)
-- Dependencies: 231
-- Name: branding_id_branding_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.branding_id_branding_seq OWNED BY public.branding.id_branding;


--
-- TOC entry 247 (class 1259 OID 45136)
-- Name: clasificacion_intenciones_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.clasificacion_intenciones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clasificacion_intenciones_id_seq OWNER TO netadmin;

--
-- TOC entry 246 (class 1259 OID 45131)
-- Name: clasificacion_intenciones; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.clasificacion_intenciones (
    id integer DEFAULT nextval('public.clasificacion_intenciones_id_seq'::regclass) NOT NULL,
    telefono character varying(20) NOT NULL,
    clasificacion character varying(100),
    estado character varying(50),
    emisor character varying(100),
    pregunta text,
    respuesta text,
    tipo_mensaje character varying(50),
    entitites text
);


ALTER TABLE public.clasificacion_intenciones OWNER TO netadmin;

--
-- TOC entry 237 (class 1259 OID 44783)
-- Name: clasificacion_intenciones_futuras; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.clasificacion_intenciones_futuras (
    telefono character varying(20) NOT NULL,
    intencion_futura text NOT NULL,
    fecha_actualizacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    observaciones text,
    mensaje_chatbot text,
    mensaje_usuario text,
    datos_promocion jsonb
);


ALTER TABLE public.clasificacion_intenciones_futuras OWNER TO netadmin;

--
-- TOC entry 211 (class 1259 OID 35881)
-- Name: clientes; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.clientes (
    idcliente integer NOT NULL,
    nombre_cliente character varying(255) NOT NULL,
    estado character varying(50) NOT NULL,
    num_chatbot bigint,
    slug character varying(30),
    hora_apertura character varying(10),
    hora_cierre character varying(10)
);


ALTER TABLE public.clientes OWNER TO netadmin;

--
-- TOC entry 210 (class 1259 OID 35880)
-- Name: clientes_idcliente_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.clientes_idcliente_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clientes_idcliente_seq OWNER TO netadmin;

--
-- TOC entry 5151 (class 0 OID 0)
-- Dependencies: 210
-- Name: clientes_idcliente_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.clientes_idcliente_seq OWNED BY public.clientes.idcliente;


--
-- TOC entry 223 (class 1259 OID 35999)
-- Name: clientes_whatsapp; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.clientes_whatsapp (
    id_whatsapp integer NOT NULL,
    nombre character varying(255) NOT NULL,
    telefono character varying(20) NOT NULL,
    direccion_cliente text,
    fecha_registro date DEFAULT CURRENT_DATE,
    direccion_google text,
    latitud double precision,
    longitud double precision,
    observaciones text,
    modo_entrega character varying(50),
    id_restaurante integer,
    id_sede integer,
    es_temporal boolean DEFAULT false,
    dir_primera_vez boolean,
    nombre_bool boolean,
    datos_personales boolean,
    "Tipo_Doc" text,
    "N_Doc" integer,
    email text,
    observaciones_dir character varying(50)
);


ALTER TABLE public.clientes_whatsapp OWNER TO netadmin;

--
-- TOC entry 222 (class 1259 OID 35998)
-- Name: clientes_whatsapp_id_whatsapp_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.clientes_whatsapp_id_whatsapp_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clientes_whatsapp_id_whatsapp_seq OWNER TO netadmin;

--
-- TOC entry 5152 (class 0 OID 0)
-- Dependencies: 222
-- Name: clientes_whatsapp_id_whatsapp_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.clientes_whatsapp_id_whatsapp_seq OWNED BY public.clientes_whatsapp.id_whatsapp;


--
-- TOC entry 244 (class 1259 OID 45125)
-- Name: conversaciones; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.conversaciones (
    id_conversaciones integer NOT NULL,
    conversacion jsonb NOT NULL,
    telefono text NOT NULL,
    fecha_mensaje timestamp with time zone NOT NULL,
    id_cliente integer NOT NULL
);


ALTER TABLE public.conversaciones OWNER TO netadmin;

--
-- TOC entry 245 (class 1259 OID 45130)
-- Name: conversaciones_id_conversaciones_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

ALTER TABLE public.conversaciones ALTER COLUMN id_conversaciones ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.conversaciones_id_conversaciones_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 228 (class 1259 OID 36142)
-- Name: conversaciones_whatsapp; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.conversaciones_whatsapp (
    id integer NOT NULL,
    telefono character varying(20) NOT NULL,
    mensaje_usuario text,
    clasificacion text,
    tipo_clasificacion text,
    entidades text,
    fecha timestamp with time zone,
    tipo_mensaje text,
    idcliente integer
);


ALTER TABLE public.conversaciones_whatsapp OWNER TO netadmin;

--
-- TOC entry 227 (class 1259 OID 36141)
-- Name: conversaciones_whatsapp_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.conversaciones_whatsapp_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.conversaciones_whatsapp_id_seq OWNER TO netadmin;

--
-- TOC entry 5153 (class 0 OID 0)
-- Dependencies: 227
-- Name: conversaciones_whatsapp_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.conversaciones_whatsapp_id_seq OWNED BY public.conversaciones_whatsapp.id;


--
-- TOC entry 225 (class 1259 OID 36027)
-- Name: detalle_pedido; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.detalle_pedido (
    id_detalle integer NOT NULL,
    id_producto integer NOT NULL,
    id_pedido integer NOT NULL,
    cantidad integer NOT NULL,
    total integer NOT NULL,
    especificaciones text
);


ALTER TABLE public.detalle_pedido OWNER TO netadmin;

--
-- TOC entry 251 (class 1259 OID 53445)
-- Name: disponibilidad_items; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.disponibilidad_items (
    id_disponibilidad integer NOT NULL,
    id_item integer,
    id_sede integer,
    disponible boolean DEFAULT true
);


ALTER TABLE public.disponibilidad_items OWNER TO netadmin;

--
-- TOC entry 250 (class 1259 OID 53444)
-- Name: disponibilidad_items_id_disponibilidad_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.disponibilidad_items_id_disponibilidad_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.disponibilidad_items_id_disponibilidad_seq OWNER TO netadmin;

--
-- TOC entry 5154 (class 0 OID 0)
-- Dependencies: 250
-- Name: disponibilidad_items_id_disponibilidad_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.disponibilidad_items_id_disponibilidad_seq OWNED BY public.disponibilidad_items.id_disponibilidad;


--
-- TOC entry 253 (class 1259 OID 53580)
-- Name: disponibilidad_promociones; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.disponibilidad_promociones (
    id_disponibilidad integer NOT NULL,
    id_promocion integer,
    id_sede integer,
    disponible boolean DEFAULT true
);


ALTER TABLE public.disponibilidad_promociones OWNER TO netadmin;

--
-- TOC entry 252 (class 1259 OID 53579)
-- Name: disponibilidad_promociones_id_disponibilidad_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.disponibilidad_promociones_id_disponibilidad_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.disponibilidad_promociones_id_disponibilidad_seq OWNER TO netadmin;

--
-- TOC entry 5155 (class 0 OID 0)
-- Dependencies: 252
-- Name: disponibilidad_promociones_id_disponibilidad_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.disponibilidad_promociones_id_disponibilidad_seq OWNED BY public.disponibilidad_promociones.id_disponibilidad;


--
-- TOC entry 248 (class 1259 OID 45535)
-- Name: historico_conversaciones; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.historico_conversaciones (
    id integer NOT NULL,
    telefono text NOT NULL,
    primer_mensaje timestamp with time zone NOT NULL,
    ultimo_mensaje timestamp with time zone,
    cantidad_mensajes integer,
    id_cliente integer NOT NULL
);


ALTER TABLE public.historico_conversaciones OWNER TO netadmin;

--
-- TOC entry 249 (class 1259 OID 45549)
-- Name: historico_conversaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.historico_conversaciones_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.historico_conversaciones_id_seq OWNER TO netadmin;

--
-- TOC entry 5156 (class 0 OID 0)
-- Dependencies: 249
-- Name: historico_conversaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.historico_conversaciones_id_seq OWNED BY public.historico_conversaciones.id;


--
-- TOC entry 226 (class 1259 OID 36122)
-- Name: id_whatsapp_messages; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.id_whatsapp_messages (
    id_messages text
);


ALTER TABLE public.id_whatsapp_messages OWNER TO netadmin;

--
-- TOC entry 221 (class 1259 OID 35982)
-- Name: items; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.items (
    iditem integer NOT NULL,
    nombre character varying(255) NOT NULL,
    precio integer NOT NULL,
    descripcion text,
    idcliente integer NOT NULL,
    estado boolean DEFAULT false NOT NULL,
    tipo_comida text,
    observaciones text DEFAULT 'normal'::text NOT NULL,
    orden text
);


ALTER TABLE public.items OWNER TO netadmin;

--
-- TOC entry 220 (class 1259 OID 35981)
-- Name: items_iditem_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.items_iditem_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.items_iditem_seq OWNER TO netadmin;

--
-- TOC entry 5157 (class 0 OID 0)
-- Dependencies: 220
-- Name: items_iditem_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.items_iditem_seq OWNED BY public.items.iditem;


--
-- TOC entry 219 (class 1259 OID 35948)
-- Name: logs; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.logs (
    idlogs integer NOT NULL,
    ambiente character varying(50),
    tipo character varying(50),
    mensaje text,
    fecha timestamp without time zone,
    idusuario integer,
    "archivoPy" character varying(40),
    function character varying(50),
    "lineNumber" integer,
    telefono text
);


ALTER TABLE public.logs OWNER TO netadmin;

--
-- TOC entry 218 (class 1259 OID 35947)
-- Name: logs_idlogs_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.logs_idlogs_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.logs_idlogs_seq OWNER TO netadmin;

--
-- TOC entry 5158 (class 0 OID 0)
-- Dependencies: 218
-- Name: logs_idlogs_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.logs_idlogs_seq OWNED BY public.logs.idlogs;


--
-- TOC entry 236 (class 1259 OID 44710)
-- Name: mensajes; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.mensajes (
    id integer NOT NULL,
    telefono character varying(20) NOT NULL,
    mensaje text,
    clasificacion text,
    intencion text,
    tipo_mensaje text,
    entidades jsonb,
    "timestamp" timestamp without time zone DEFAULT now(),
    id_restaurante integer NOT NULL
);


ALTER TABLE public.mensajes OWNER TO netadmin;

--
-- TOC entry 235 (class 1259 OID 44709)
-- Name: mensajes_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.mensajes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.mensajes_id_seq OWNER TO netadmin;

--
-- TOC entry 5159 (class 0 OID 0)
-- Dependencies: 235
-- Name: mensajes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.mensajes_id_seq OWNED BY public.mensajes.id;


--
-- TOC entry 224 (class 1259 OID 36026)
-- Name: ordenes_idorden_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.ordenes_idorden_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ordenes_idorden_seq OWNER TO netadmin;

--
-- TOC entry 5160 (class 0 OID 0)
-- Dependencies: 224
-- Name: ordenes_idorden_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.ordenes_idorden_seq OWNED BY public.detalle_pedido.id_detalle;


--
-- TOC entry 217 (class 1259 OID 35918)
-- Name: pedidos; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.pedidos (
    idpedido integer NOT NULL,
    total_productos numeric(20,2) NOT NULL,
    fecha timestamp without time zone NOT NULL,
    hora character varying(50),
    idcliente integer NOT NULL,
    idsede integer NOT NULL,
    estado character varying(50),
    persona_nuevo boolean,
    id_whatsapp integer NOT NULL,
    distancia numeric,
    tiempo_estimado character varying(20),
    metodo_pago character varying(30),
    codigo_unico character varying(30),
    total_domicilio numeric(10,0),
    total_final numeric(10,0),
    es_temporal boolean DEFAULT false,
    es_promocion boolean DEFAULT false,
    id_pago character varying(200),
    direccion character varying,
    metodo_entrega character varying(30)
);


ALTER TABLE public.pedidos OWNER TO netadmin;

--
-- TOC entry 216 (class 1259 OID 35917)
-- Name: pedidos_idpedido_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.pedidos_idpedido_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pedidos_idpedido_seq OWNER TO netadmin;

--
-- TOC entry 5161 (class 0 OID 0)
-- Dependencies: 216
-- Name: pedidos_idpedido_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.pedidos_idpedido_seq OWNED BY public.pedidos.idpedido;


--
-- TOC entry 230 (class 1259 OID 36202)
-- Name: promociones; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.promociones (
    idpromocion integer NOT NULL,
    nombre text NOT NULL,
    descripcion text,
    precio numeric(10,2),
    idcliente integer,
    idsede integer,
    fecha_inicio date,
    fecha_fin date,
    estado text,
    descuento numeric(10,2),
    porcentaje text,
    precio_original numeric(10,2)
);


ALTER TABLE public.promociones OWNER TO netadmin;

--
-- TOC entry 229 (class 1259 OID 36201)
-- Name: promociones_idpromocion_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.promociones_idpromocion_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.promociones_idpromocion_seq OWNER TO netadmin;

--
-- TOC entry 5162 (class 0 OID 0)
-- Dependencies: 229
-- Name: promociones_idpromocion_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.promociones_idpromocion_seq OWNED BY public.promociones.idpromocion;


--
-- TOC entry 239 (class 1259 OID 44837)
-- Name: pruebas_api; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.pruebas_api (
    id integer NOT NULL,
    mensaje text NOT NULL,
    respuesta text,
    tokens integer,
    clasificacion text,
    rpersona text,
    fecha date
);


ALTER TABLE public.pruebas_api OWNER TO netadmin;

--
-- TOC entry 238 (class 1259 OID 44836)
-- Name: pruebas_api_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.pruebas_api_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pruebas_api_id_seq OWNER TO netadmin;

--
-- TOC entry 5163 (class 0 OID 0)
-- Dependencies: 238
-- Name: pruebas_api_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.pruebas_api_id_seq OWNED BY public.pruebas_api.id;


--
-- TOC entry 241 (class 1259 OID 44925)
-- Name: quejas; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.quejas (
    id integer NOT NULL,
    sender character varying(20) NOT NULL,
    queja_original text NOT NULL,
    entidades jsonb,
    respuesta_agente text,
    fecha_hora timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.quejas OWNER TO netadmin;

--
-- TOC entry 243 (class 1259 OID 44935)
-- Name: quejas_graves; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.quejas_graves (
    id integer NOT NULL,
    sender character varying(30) NOT NULL,
    queja_original text NOT NULL,
    entidades jsonb,
    respuesta_agente text NOT NULL,
    accion_recomendada text NOT NULL,
    resumen_ejecutivo text NOT NULL,
    fecha_hora timestamp without time zone DEFAULT now()
);


ALTER TABLE public.quejas_graves OWNER TO netadmin;

--
-- TOC entry 242 (class 1259 OID 44934)
-- Name: quejas_graves_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.quejas_graves_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.quejas_graves_id_seq OWNER TO netadmin;

--
-- TOC entry 5164 (class 0 OID 0)
-- Dependencies: 242
-- Name: quejas_graves_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.quejas_graves_id_seq OWNED BY public.quejas_graves.id;


--
-- TOC entry 240 (class 1259 OID 44924)
-- Name: quejas_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.quejas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.quejas_id_seq OWNER TO netadmin;

--
-- TOC entry 5165 (class 0 OID 0)
-- Dependencies: 240
-- Name: quejas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.quejas_id_seq OWNED BY public.quejas.id;


--
-- TOC entry 215 (class 1259 OID 35904)
-- Name: sedes; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.sedes (
    id_sede integer NOT NULL,
    direccion character varying(500) NOT NULL,
    nombre character varying(255) NOT NULL,
    ciudad character varying(100) NOT NULL,
    telefono character varying(20),
    correo character varying(255),
    id_restaurante integer NOT NULL,
    latitud double precision,
    longitud double precision,
    estado boolean,
    horarios jsonb,
    num_admin character varying(15)
);


ALTER TABLE public.sedes OWNER TO netadmin;

--
-- TOC entry 234 (class 1259 OID 44640)
-- Name: sedes_areas; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.sedes_areas (
    id integer NOT NULL,
    id_sede integer NOT NULL,
    valor text NOT NULL,
    prioridad integer,
    costo_domicilio numeric,
    hora_inicio integer,
    hora_fin integer,
    geom public.geometry(Polygon,4326)
);


ALTER TABLE public.sedes_areas OWNER TO netadmin;

--
-- TOC entry 233 (class 1259 OID 44639)
-- Name: sedes_areas_id_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.sedes_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sedes_areas_id_seq OWNER TO netadmin;

--
-- TOC entry 5166 (class 0 OID 0)
-- Dependencies: 233
-- Name: sedes_areas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.sedes_areas_id_seq OWNED BY public.sedes_areas.id;


--
-- TOC entry 214 (class 1259 OID 35903)
-- Name: sedes_idsede_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.sedes_idsede_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sedes_idsede_seq OWNER TO netadmin;

--
-- TOC entry 5167 (class 0 OID 0)
-- Dependencies: 214
-- Name: sedes_idsede_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.sedes_idsede_seq OWNED BY public.sedes.id_sede;


--
-- TOC entry 213 (class 1259 OID 35888)
-- Name: usuarios; Type: TABLE; Schema: public; Owner: netadmin
--

CREATE TABLE public.usuarios (
    id_usuario integer NOT NULL,
    nombre_completo character varying(255) NOT NULL,
    correo character varying(255) NOT NULL,
    contrasena character varying(255) NOT NULL,
    salt character varying(255) NOT NULL,
    tipo_usuario character varying(50) NOT NULL,
    estado character varying(50) NOT NULL,
    codigo character varying(100),
    idcliente integer NOT NULL,
    idsede integer,
    uso_codigo boolean,
    subdominio character varying(50)
);


ALTER TABLE public.usuarios OWNER TO netadmin;

--
-- TOC entry 212 (class 1259 OID 35887)
-- Name: usuarios_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: netadmin
--

CREATE SEQUENCE public.usuarios_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usuarios_id_usuario_seq OWNER TO netadmin;

--
-- TOC entry 5169 (class 0 OID 0)
-- Dependencies: 212
-- Name: usuarios_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: netadmin
--

ALTER SEQUENCE public.usuarios_id_usuario_seq OWNED BY public.usuarios.id_usuario;


--
-- TOC entry 4816 (class 2604 OID 44356)
-- Name: branding id_branding; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.branding ALTER COLUMN id_branding SET DEFAULT nextval('public.branding_id_branding_seq'::regclass);


--
-- TOC entry 4800 (class 2604 OID 35884)
-- Name: clientes idcliente; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes ALTER COLUMN idcliente SET DEFAULT nextval('public.clientes_idcliente_seq'::regclass);


--
-- TOC entry 4810 (class 2604 OID 36002)
-- Name: clientes_whatsapp id_whatsapp; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes_whatsapp ALTER COLUMN id_whatsapp SET DEFAULT nextval('public.clientes_whatsapp_id_whatsapp_seq'::regclass);


--
-- TOC entry 4814 (class 2604 OID 36145)
-- Name: conversaciones_whatsapp id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.conversaciones_whatsapp ALTER COLUMN id SET DEFAULT nextval('public.conversaciones_whatsapp_id_seq'::regclass);


--
-- TOC entry 4813 (class 2604 OID 36030)
-- Name: detalle_pedido id_detalle; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.detalle_pedido ALTER COLUMN id_detalle SET DEFAULT nextval('public.ordenes_idorden_seq'::regclass);


--
-- TOC entry 4828 (class 2604 OID 53448)
-- Name: disponibilidad_items id_disponibilidad; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_items ALTER COLUMN id_disponibilidad SET DEFAULT nextval('public.disponibilidad_items_id_disponibilidad_seq'::regclass);


--
-- TOC entry 4830 (class 2604 OID 53583)
-- Name: disponibilidad_promociones id_disponibilidad; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_promociones ALTER COLUMN id_disponibilidad SET DEFAULT nextval('public.disponibilidad_promociones_id_disponibilidad_seq'::regclass);


--
-- TOC entry 4827 (class 2604 OID 45550)
-- Name: historico_conversaciones id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.historico_conversaciones ALTER COLUMN id SET DEFAULT nextval('public.historico_conversaciones_id_seq'::regclass);


--
-- TOC entry 4807 (class 2604 OID 35985)
-- Name: items iditem; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.items ALTER COLUMN iditem SET DEFAULT nextval('public.items_iditem_seq'::regclass);


--
-- TOC entry 4806 (class 2604 OID 35951)
-- Name: logs idlogs; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.logs ALTER COLUMN idlogs SET DEFAULT nextval('public.logs_idlogs_seq'::regclass);


--
-- TOC entry 4818 (class 2604 OID 44713)
-- Name: mensajes id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.mensajes ALTER COLUMN id SET DEFAULT nextval('public.mensajes_id_seq'::regclass);


--
-- TOC entry 4803 (class 2604 OID 35921)
-- Name: pedidos idpedido; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pedidos ALTER COLUMN idpedido SET DEFAULT nextval('public.pedidos_idpedido_seq'::regclass);


--
-- TOC entry 4815 (class 2604 OID 36205)
-- Name: promociones idpromocion; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.promociones ALTER COLUMN idpromocion SET DEFAULT nextval('public.promociones_idpromocion_seq'::regclass);


--
-- TOC entry 4821 (class 2604 OID 44840)
-- Name: pruebas_api id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pruebas_api ALTER COLUMN id SET DEFAULT nextval('public.pruebas_api_id_seq'::regclass);


--
-- TOC entry 4822 (class 2604 OID 44928)
-- Name: quejas id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.quejas ALTER COLUMN id SET DEFAULT nextval('public.quejas_id_seq'::regclass);


--
-- TOC entry 4824 (class 2604 OID 44938)
-- Name: quejas_graves id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.quejas_graves ALTER COLUMN id SET DEFAULT nextval('public.quejas_graves_id_seq'::regclass);


--
-- TOC entry 4802 (class 2604 OID 35907)
-- Name: sedes id_sede; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.sedes ALTER COLUMN id_sede SET DEFAULT nextval('public.sedes_idsede_seq'::regclass);


--
-- TOC entry 4817 (class 2604 OID 44643)
-- Name: sedes_areas id; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.sedes_areas ALTER COLUMN id SET DEFAULT nextval('public.sedes_areas_id_seq'::regclass);


--
-- TOC entry 4801 (class 2604 OID 35891)
-- Name: usuarios id_usuario; Type: DEFAULT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuarios_id_usuario_seq'::regclass);


--
-- TOC entry 4869 (class 2606 OID 44360)
-- Name: branding branding_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.branding
    ADD CONSTRAINT branding_pkey PRIMARY KEY (id_branding);


--
-- TOC entry 4876 (class 2606 OID 44788)
-- Name: clasificacion_intenciones_futuras clasificacion_intenciones_futuras_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clasificacion_intenciones_futuras
    ADD CONSTRAINT clasificacion_intenciones_futuras_pkey PRIMARY KEY (telefono);


--
-- TOC entry 4834 (class 2606 OID 35886)
-- Name: clientes clientes_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pkey PRIMARY KEY (idcliente);


--
-- TOC entry 4856 (class 2606 OID 36007)
-- Name: clientes_whatsapp clientes_whatsapp_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes_whatsapp
    ADD CONSTRAINT clientes_whatsapp_pkey PRIMARY KEY (id_whatsapp);


--
-- TOC entry 4858 (class 2606 OID 44732)
-- Name: clientes_whatsapp clientes_whatsapp_telefono_unique; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes_whatsapp
    ADD CONSTRAINT clientes_whatsapp_telefono_unique UNIQUE (telefono);


--
-- TOC entry 4884 (class 2606 OID 45543)
-- Name: conversaciones conversaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.conversaciones
    ADD CONSTRAINT conversaciones_pkey PRIMARY KEY (id_conversaciones);


--
-- TOC entry 4862 (class 2606 OID 36149)
-- Name: conversaciones_whatsapp conversaciones_whatsapp_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.conversaciones_whatsapp
    ADD CONSTRAINT conversaciones_whatsapp_pkey PRIMARY KEY (id);


--
-- TOC entry 4890 (class 2606 OID 53451)
-- Name: disponibilidad_items disponibilidad_items_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_items
    ADD CONSTRAINT disponibilidad_items_pkey PRIMARY KEY (id_disponibilidad);


--
-- TOC entry 4896 (class 2606 OID 53586)
-- Name: disponibilidad_promociones disponibilidad_promociones_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_promociones
    ADD CONSTRAINT disponibilidad_promociones_pkey PRIMARY KEY (id_disponibilidad);


--
-- TOC entry 4887 (class 2606 OID 45541)
-- Name: historico_conversaciones historico_conversaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.historico_conversaciones
    ADD CONSTRAINT historico_conversaciones_pkey PRIMARY KEY (id);


--
-- TOC entry 4854 (class 2606 OID 35989)
-- Name: items items_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_pkey PRIMARY KEY (iditem);


--
-- TOC entry 4852 (class 2606 OID 35955)
-- Name: logs logs_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.logs
    ADD CONSTRAINT logs_pkey PRIMARY KEY (idlogs);


--
-- TOC entry 4874 (class 2606 OID 44718)
-- Name: mensajes mensajes_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.mensajes
    ADD CONSTRAINT mensajes_pkey PRIMARY KEY (id);


--
-- TOC entry 4860 (class 2606 OID 36034)
-- Name: detalle_pedido ordenes_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.detalle_pedido
    ADD CONSTRAINT ordenes_pkey PRIMARY KEY (id_detalle);


--
-- TOC entry 4850 (class 2606 OID 35925)
-- Name: pedidos pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_pkey PRIMARY KEY (idpedido);


--
-- TOC entry 4867 (class 2606 OID 36209)
-- Name: promociones promociones_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.promociones
    ADD CONSTRAINT promociones_pkey PRIMARY KEY (idpromocion);


--
-- TOC entry 4878 (class 2606 OID 44844)
-- Name: pruebas_api pruebas_api_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pruebas_api
    ADD CONSTRAINT pruebas_api_pkey PRIMARY KEY (id);


--
-- TOC entry 4882 (class 2606 OID 44943)
-- Name: quejas_graves quejas_graves_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.quejas_graves
    ADD CONSTRAINT quejas_graves_pkey PRIMARY KEY (id);


--
-- TOC entry 4880 (class 2606 OID 44933)
-- Name: quejas quejas_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.quejas
    ADD CONSTRAINT quejas_pkey PRIMARY KEY (id);


--
-- TOC entry 4872 (class 2606 OID 44647)
-- Name: sedes_areas sedes_areas_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.sedes_areas
    ADD CONSTRAINT sedes_areas_pkey PRIMARY KEY (id);


--
-- TOC entry 4843 (class 2606 OID 35911)
-- Name: sedes sedes_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.sedes
    ADD CONSTRAINT sedes_pkey PRIMARY KEY (id_sede);


--
-- TOC entry 4894 (class 2606 OID 53453)
-- Name: disponibilidad_items unique_item_sede; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_items
    ADD CONSTRAINT unique_item_sede UNIQUE (id_item, id_sede);


--
-- TOC entry 4900 (class 2606 OID 53588)
-- Name: disponibilidad_promociones unique_promo_sede; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_promociones
    ADD CONSTRAINT unique_promo_sede UNIQUE (id_promocion, id_sede);


--
-- TOC entry 4838 (class 2606 OID 35897)
-- Name: usuarios usuarios_correo_key; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_correo_key UNIQUE (correo);


--
-- TOC entry 4840 (class 2606 OID 35895)
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id_usuario);


--
-- TOC entry 4885 (class 1259 OID 56730)
-- Name: idx_conversaciones_telefono; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_conversaciones_telefono ON public.conversaciones USING btree (telefono);


--
-- TOC entry 4891 (class 1259 OID 53464)
-- Name: idx_disp_item; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_disp_item ON public.disponibilidad_items USING btree (id_item);


--
-- TOC entry 4897 (class 1259 OID 53599)
-- Name: idx_disp_promo_id; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_disp_promo_id ON public.disponibilidad_promociones USING btree (id_promocion);


--
-- TOC entry 4898 (class 1259 OID 53600)
-- Name: idx_disp_promo_sede; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_disp_promo_sede ON public.disponibilidad_promociones USING btree (id_sede);


--
-- TOC entry 4892 (class 1259 OID 53465)
-- Name: idx_disp_sede; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_disp_sede ON public.disponibilidad_items USING btree (id_sede);


--
-- TOC entry 4888 (class 1259 OID 56731)
-- Name: idx_historico_telefono; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_historico_telefono ON public.historico_conversaciones USING btree (telefono);


--
-- TOC entry 4844 (class 1259 OID 44686)
-- Name: idx_pedidos_estado; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_pedidos_estado ON public.pedidos USING btree (estado);


--
-- TOC entry 4845 (class 1259 OID 35934)
-- Name: idx_pedidos_fecha; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_pedidos_fecha ON public.pedidos USING btree (fecha);


--
-- TOC entry 4846 (class 1259 OID 35935)
-- Name: idx_pedidos_id_usuario; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_pedidos_id_usuario ON public.pedidos USING btree (idcliente);


--
-- TOC entry 4847 (class 1259 OID 44685)
-- Name: idx_pedidos_idcliente_idsede_fecha; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_pedidos_idcliente_idsede_fecha ON public.pedidos USING btree (idcliente, idsede, fecha);


--
-- TOC entry 4848 (class 1259 OID 44312)
-- Name: idx_pedidos_idsede_fecha; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_pedidos_idsede_fecha ON public.pedidos USING btree (idsede, fecha);


--
-- TOC entry 4863 (class 1259 OID 36220)
-- Name: idx_promociones_cliente; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_promociones_cliente ON public.promociones USING btree (idcliente);


--
-- TOC entry 4864 (class 1259 OID 36222)
-- Name: idx_promociones_fechas; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_promociones_fechas ON public.promociones USING btree (fecha_inicio, fecha_fin);


--
-- TOC entry 4865 (class 1259 OID 36221)
-- Name: idx_promociones_sede; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_promociones_sede ON public.promociones USING btree (idsede);


--
-- TOC entry 4870 (class 1259 OID 55820)
-- Name: idx_sedes_areas_geom; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_sedes_areas_geom ON public.sedes_areas USING gist (geom);


--
-- TOC entry 4841 (class 1259 OID 35933)
-- Name: idx_sedes_idcliente; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_sedes_idcliente ON public.sedes USING btree (id_restaurante);


--
-- TOC entry 4835 (class 1259 OID 35931)
-- Name: idx_usuarios_correo; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_usuarios_correo ON public.usuarios USING btree (correo);


--
-- TOC entry 4836 (class 1259 OID 35932)
-- Name: idx_usuarios_idcliente; Type: INDEX; Schema: public; Owner: netadmin
--

CREATE INDEX idx_usuarios_idcliente ON public.usuarios USING btree (idcliente);


--
-- TOC entry 4919 (class 2606 OID 45544)
-- Name: conversaciones conversaciones_id_cliente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.conversaciones
    ADD CONSTRAINT conversaciones_id_cliente_fkey FOREIGN KEY (id_cliente) REFERENCES public.clientes(idcliente) NOT VALID;


--
-- TOC entry 4913 (class 2606 OID 45182)
-- Name: detalle_pedido detalle_pedido_id_pedido_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.detalle_pedido
    ADD CONSTRAINT detalle_pedido_id_pedido_fkey FOREIGN KEY (id_pedido) REFERENCES public.pedidos(idpedido) NOT VALID;


--
-- TOC entry 4914 (class 2606 OID 45177)
-- Name: detalle_pedido detalle_pedido_id_producto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.detalle_pedido
    ADD CONSTRAINT detalle_pedido_id_producto_fkey FOREIGN KEY (id_producto) REFERENCES public.items(iditem) NOT VALID;


--
-- TOC entry 4920 (class 2606 OID 53454)
-- Name: disponibilidad_items disponibilidad_items_id_item_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_items
    ADD CONSTRAINT disponibilidad_items_id_item_fkey FOREIGN KEY (id_item) REFERENCES public.items(iditem) ON DELETE CASCADE;


--
-- TOC entry 4921 (class 2606 OID 53459)
-- Name: disponibilidad_items disponibilidad_items_id_sede_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_items
    ADD CONSTRAINT disponibilidad_items_id_sede_fkey FOREIGN KEY (id_sede) REFERENCES public.sedes(id_sede) ON DELETE CASCADE;


--
-- TOC entry 4922 (class 2606 OID 53589)
-- Name: disponibilidad_promociones disponibilidad_promociones_id_promocion_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_promociones
    ADD CONSTRAINT disponibilidad_promociones_id_promocion_fkey FOREIGN KEY (id_promocion) REFERENCES public.promociones(idpromocion) ON DELETE CASCADE;


--
-- TOC entry 4923 (class 2606 OID 53594)
-- Name: disponibilidad_promociones disponibilidad_promociones_id_sede_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.disponibilidad_promociones
    ADD CONSTRAINT disponibilidad_promociones_id_sede_fkey FOREIGN KEY (id_sede) REFERENCES public.sedes(id_sede) ON DELETE CASCADE;


--
-- TOC entry 4917 (class 2606 OID 44361)
-- Name: branding fk_branding_cliente; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.branding
    ADD CONSTRAINT fk_branding_cliente FOREIGN KEY (idcliente) REFERENCES public.clientes(idcliente) ON DELETE CASCADE;


--
-- TOC entry 4911 (class 2606 OID 36008)
-- Name: clientes_whatsapp fk_cliente; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes_whatsapp
    ADD CONSTRAINT fk_cliente FOREIGN KEY (id_restaurante) REFERENCES public.clientes(idcliente) ON DELETE SET NULL;


--
-- TOC entry 4910 (class 2606 OID 35990)
-- Name: items fk_items_clientes; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT fk_items_clientes FOREIGN KEY (idcliente) REFERENCES public.clientes(idcliente);


--
-- TOC entry 4909 (class 2606 OID 35956)
-- Name: logs fk_logs_clientes; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.logs
    ADD CONSTRAINT fk_logs_clientes FOREIGN KEY (idusuario) REFERENCES public.clientes(idcliente) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- TOC entry 4906 (class 2606 OID 36018)
-- Name: pedidos fk_pedidos_clientes_whatsapp; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT fk_pedidos_clientes_whatsapp FOREIGN KEY (id_whatsapp) REFERENCES public.clientes_whatsapp(id_whatsapp) ON DELETE SET NULL;


--
-- TOC entry 4915 (class 2606 OID 36210)
-- Name: promociones fk_promociones_cliente; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.promociones
    ADD CONSTRAINT fk_promociones_cliente FOREIGN KEY (idcliente) REFERENCES public.clientes(idcliente) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- TOC entry 4916 (class 2606 OID 36215)
-- Name: promociones fk_promociones_sede; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.promociones
    ADD CONSTRAINT fk_promociones_sede FOREIGN KEY (idsede) REFERENCES public.sedes(id_sede) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- TOC entry 4912 (class 2606 OID 36013)
-- Name: clientes_whatsapp fk_sede; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.clientes_whatsapp
    ADD CONSTRAINT fk_sede FOREIGN KEY (id_sede) REFERENCES public.sedes(id_sede) ON DELETE SET NULL;


--
-- TOC entry 4903 (class 2606 OID 35936)
-- Name: usuarios fk_usuarios_sede; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT fk_usuarios_sede FOREIGN KEY (idsede) REFERENCES public.sedes(id_sede) ON DELETE SET NULL;


--
-- TOC entry 4907 (class 2606 OID 35971)
-- Name: pedidos id_cliente; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT id_cliente FOREIGN KEY (idcliente) REFERENCES public.clientes(idcliente) NOT VALID;


--
-- TOC entry 4908 (class 2606 OID 35976)
-- Name: pedidos idpedido; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT idpedido FOREIGN KEY (idpedido) REFERENCES public.pedidos(idpedido) NOT VALID;


--
-- TOC entry 4918 (class 2606 OID 44648)
-- Name: sedes_areas sedes_areas_id_sede_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.sedes_areas
    ADD CONSTRAINT sedes_areas_id_sede_fkey FOREIGN KEY (id_sede) REFERENCES public.sedes(id_sede) ON DELETE CASCADE;


--
-- TOC entry 4905 (class 2606 OID 35912)
-- Name: sedes sedes_idcliente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.sedes
    ADD CONSTRAINT sedes_idcliente_fkey FOREIGN KEY (id_restaurante) REFERENCES public.clientes(idcliente) ON DELETE CASCADE;


--
-- TOC entry 4904 (class 2606 OID 35898)
-- Name: usuarios usuarios_idcliente_fkey; Type: FK CONSTRAINT; Schema: public; Owner: netadmin
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_idcliente_fkey FOREIGN KEY (idcliente) REFERENCES public.clientes(idcliente) ON DELETE CASCADE;


--
-- TOC entry 5073 (class 0 OID 0)
-- Dependencies: 6
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: azure_pg_admin
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- TOC entry 5075 (class 0 OID 0)
-- Dependencies: 259
-- Name: FUNCTION pg_replication_origin_advance(text, pg_lsn); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_advance(text, pg_lsn) TO azure_pg_admin;


--
-- TOC entry 5076 (class 0 OID 0)
-- Dependencies: 303
-- Name: FUNCTION pg_replication_origin_create(text); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_create(text) TO azure_pg_admin;


--
-- TOC entry 5077 (class 0 OID 0)
-- Dependencies: 304
-- Name: FUNCTION pg_replication_origin_drop(text); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_drop(text) TO azure_pg_admin;


--
-- TOC entry 5078 (class 0 OID 0)
-- Dependencies: 320
-- Name: FUNCTION pg_replication_origin_oid(text); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_oid(text) TO azure_pg_admin;


--
-- TOC entry 5079 (class 0 OID 0)
-- Dependencies: 325
-- Name: FUNCTION pg_replication_origin_progress(text, boolean); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_progress(text, boolean) TO azure_pg_admin;


--
-- TOC entry 5080 (class 0 OID 0)
-- Dependencies: 326
-- Name: FUNCTION pg_replication_origin_session_is_setup(); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_session_is_setup() TO azure_pg_admin;


--
-- TOC entry 5081 (class 0 OID 0)
-- Dependencies: 260
-- Name: FUNCTION pg_replication_origin_session_progress(boolean); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_session_progress(boolean) TO azure_pg_admin;


--
-- TOC entry 5082 (class 0 OID 0)
-- Dependencies: 321
-- Name: FUNCTION pg_replication_origin_session_reset(); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_session_reset() TO azure_pg_admin;


--
-- TOC entry 5083 (class 0 OID 0)
-- Dependencies: 327
-- Name: FUNCTION pg_replication_origin_session_setup(text); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_session_setup(text) TO azure_pg_admin;


--
-- TOC entry 5084 (class 0 OID 0)
-- Dependencies: 328
-- Name: FUNCTION pg_replication_origin_xact_reset(); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_xact_reset() TO azure_pg_admin;


--
-- TOC entry 5085 (class 0 OID 0)
-- Dependencies: 329
-- Name: FUNCTION pg_replication_origin_xact_setup(pg_lsn, timestamp with time zone); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_replication_origin_xact_setup(pg_lsn, timestamp with time zone) TO azure_pg_admin;


--
-- TOC entry 5086 (class 0 OID 0)
-- Dependencies: 330
-- Name: FUNCTION pg_show_replication_origin_status(OUT local_id oid, OUT external_id text, OUT remote_lsn pg_lsn, OUT local_lsn pg_lsn); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_show_replication_origin_status(OUT local_id oid, OUT external_id text, OUT remote_lsn pg_lsn, OUT local_lsn pg_lsn) TO azure_pg_admin;


--
-- TOC entry 5087 (class 0 OID 0)
-- Dependencies: 261
-- Name: FUNCTION pg_stat_reset(); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_stat_reset() TO azure_pg_admin;


--
-- TOC entry 5088 (class 0 OID 0)
-- Dependencies: 277
-- Name: FUNCTION pg_stat_reset_shared(text); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_stat_reset_shared(text) TO azure_pg_admin;


--
-- TOC entry 5089 (class 0 OID 0)
-- Dependencies: 278
-- Name: FUNCTION pg_stat_reset_single_function_counters(oid); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_stat_reset_single_function_counters(oid) TO azure_pg_admin;


--
-- TOC entry 5090 (class 0 OID 0)
-- Dependencies: 262
-- Name: FUNCTION pg_stat_reset_single_table_counters(oid); Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT ALL ON FUNCTION pg_catalog.pg_stat_reset_single_table_counters(oid) TO azure_pg_admin;


--
-- TOC entry 5091 (class 0 OID 0)
-- Dependencies: 96
-- Name: COLUMN pg_config.name; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(name) ON TABLE pg_catalog.pg_config TO azure_pg_admin;


--
-- TOC entry 5092 (class 0 OID 0)
-- Dependencies: 96
-- Name: COLUMN pg_config.setting; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(setting) ON TABLE pg_catalog.pg_config TO azure_pg_admin;


--
-- TOC entry 5093 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.line_number; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(line_number) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5094 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.type; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(type) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5095 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.database; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(database) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5096 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.user_name; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(user_name) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5097 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.address; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(address) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5098 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.netmask; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(netmask) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5099 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.auth_method; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(auth_method) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5100 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.options; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(options) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5101 (class 0 OID 0)
-- Dependencies: 93
-- Name: COLUMN pg_hba_file_rules.error; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(error) ON TABLE pg_catalog.pg_hba_file_rules TO azure_pg_admin;


--
-- TOC entry 5102 (class 0 OID 0)
-- Dependencies: 140
-- Name: COLUMN pg_replication_origin_status.local_id; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(local_id) ON TABLE pg_catalog.pg_replication_origin_status TO azure_pg_admin;


--
-- TOC entry 5103 (class 0 OID 0)
-- Dependencies: 140
-- Name: COLUMN pg_replication_origin_status.external_id; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(external_id) ON TABLE pg_catalog.pg_replication_origin_status TO azure_pg_admin;


--
-- TOC entry 5104 (class 0 OID 0)
-- Dependencies: 140
-- Name: COLUMN pg_replication_origin_status.remote_lsn; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(remote_lsn) ON TABLE pg_catalog.pg_replication_origin_status TO azure_pg_admin;


--
-- TOC entry 5105 (class 0 OID 0)
-- Dependencies: 140
-- Name: COLUMN pg_replication_origin_status.local_lsn; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(local_lsn) ON TABLE pg_catalog.pg_replication_origin_status TO azure_pg_admin;


--
-- TOC entry 5106 (class 0 OID 0)
-- Dependencies: 97
-- Name: COLUMN pg_shmem_allocations.name; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(name) ON TABLE pg_catalog.pg_shmem_allocations TO azure_pg_admin;


--
-- TOC entry 5107 (class 0 OID 0)
-- Dependencies: 97
-- Name: COLUMN pg_shmem_allocations.off; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(off) ON TABLE pg_catalog.pg_shmem_allocations TO azure_pg_admin;


--
-- TOC entry 5108 (class 0 OID 0)
-- Dependencies: 97
-- Name: COLUMN pg_shmem_allocations.size; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(size) ON TABLE pg_catalog.pg_shmem_allocations TO azure_pg_admin;


--
-- TOC entry 5109 (class 0 OID 0)
-- Dependencies: 97
-- Name: COLUMN pg_shmem_allocations.allocated_size; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(allocated_size) ON TABLE pg_catalog.pg_shmem_allocations TO azure_pg_admin;


--
-- TOC entry 5110 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.starelid; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(starelid) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5111 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.staattnum; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(staattnum) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5112 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stainherit; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stainherit) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5113 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stanullfrac; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stanullfrac) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5114 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stawidth; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stawidth) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5115 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stadistinct; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stadistinct) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5116 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stakind1; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stakind1) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5117 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stakind2; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stakind2) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5118 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stakind3; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stakind3) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5119 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stakind4; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stakind4) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5120 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stakind5; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stakind5) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5121 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.staop1; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(staop1) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5122 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.staop2; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(staop2) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5123 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.staop3; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(staop3) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5124 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.staop4; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(staop4) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5125 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.staop5; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(staop5) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5126 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stacoll1; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stacoll1) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5127 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stacoll2; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stacoll2) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5128 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stacoll3; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stacoll3) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5129 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stacoll4; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stacoll4) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5130 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stacoll5; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stacoll5) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5131 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stanumbers1; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stanumbers1) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5132 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stanumbers2; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stanumbers2) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5133 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stanumbers3; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stanumbers3) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5134 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stanumbers4; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stanumbers4) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5135 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stanumbers5; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stanumbers5) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5136 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stavalues1; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stavalues1) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5137 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stavalues2; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stavalues2) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5138 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stavalues3; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stavalues3) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5139 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stavalues4; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stavalues4) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5140 (class 0 OID 0)
-- Dependencies: 40
-- Name: COLUMN pg_statistic.stavalues5; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(stavalues5) ON TABLE pg_catalog.pg_statistic TO azure_pg_admin;


--
-- TOC entry 5141 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.oid; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(oid) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5142 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subdbid; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subdbid) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5143 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subname; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subname) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5144 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subowner; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subowner) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5145 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subenabled; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subenabled) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5146 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subconninfo; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subconninfo) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5147 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subslotname; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subslotname) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5148 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subsynccommit; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subsynccommit) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5149 (class 0 OID 0)
-- Dependencies: 65
-- Name: COLUMN pg_subscription.subpublications; Type: ACL; Schema: pg_catalog; Owner: azuresu
--

GRANT SELECT(subpublications) ON TABLE pg_catalog.pg_subscription TO azure_pg_admin;


--
-- TOC entry 5168 (class 0 OID 0)
-- Dependencies: 255
-- Name: TABLE spatial_ref_sys; Type: ACL; Schema: public; Owner: azuresu
--

GRANT SELECT,INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,UPDATE ON TABLE public.spatial_ref_sys TO azure_pg_admin WITH GRANT OPTION;


-- Completed on 2026-02-28 14:15:55

--
-- PostgreSQL database dump complete
--

\unrestrict 72PgmdtpzYyCwqKfaDJbv5Bvqwh2O47W0yM6Pw4hNcLrkjd89icLUTe2oYVpeCu

