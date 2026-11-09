--
-- PostgreSQL database dump
--

\restrict jZRPD0ZJR8eqpDuWoaQQAaf9VgECjSXje0Dmip6smpFiClOcFhbJaQEhhulfwnG

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

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
-- Name: shop; Type: SCHEMA; Schema: -; Owner: tmp
--

CREATE SCHEMA shop;


ALTER SCHEMA shop OWNER TO tmp;

--
-- Name: order_status; Type: TYPE; Schema: shop; Owner: tmp
--

CREATE TYPE shop.order_status AS ENUM (
    'new',
    'paid',
    'shipped'
);


ALTER TYPE shop.order_status OWNER TO tmp;

--
-- Name: touch(); Type: FUNCTION; Schema: shop; Owner: tmp
--

CREATE FUNCTION shop.touch() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- it's got apostrophes; and semicolons
  NEW.note := 'touched';
  RETURN NEW;
END;
$$;


ALTER FUNCTION shop.touch() OWNER TO tmp;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: Order Items; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop."Order Items" (
    id integer NOT NULL,
    "Customer Id" bigint NOT NULL,
    status shop.order_status DEFAULT 'new'::shop.order_status NOT NULL,
    total numeric(10,2) GENERATED ALWAYS AS ((1.0 * (2)::numeric)) STORED
);


ALTER TABLE shop."Order Items" OWNER TO tmp;

--
-- Name: Order Items_id_seq; Type: SEQUENCE; Schema: shop; Owner: tmp
--

CREATE SEQUENCE shop."Order Items_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE shop."Order Items_id_seq" OWNER TO tmp;

--
-- Name: Order Items_id_seq; Type: SEQUENCE OWNED BY; Schema: shop; Owner: tmp
--

ALTER SEQUENCE shop."Order Items_id_seq" OWNED BY shop."Order Items".id;


--
-- Name: customers; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.customers (
    id bigint NOT NULL,
    email character varying(255) NOT NULL,
    tags text[] DEFAULT '{}'::text[],
    scores integer[],
    balance numeric(12,2) DEFAULT '-1.50'::numeric NOT NULL,
    referred_by bigint,
    created_at timestamp with time zone DEFAULT now(),
    note text DEFAULT 'it''s new'::text,
    CONSTRAINT customers_balance_check CHECK ((balance >= ('-100'::integer)::numeric))
);


ALTER TABLE shop.customers OWNER TO tmp;

--
-- Name: TABLE customers; Type: COMMENT; Schema: shop; Owner: tmp
--

COMMENT ON TABLE shop.customers IS 'People who''ve bought things';


--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: shop; Owner: tmp
--

ALTER TABLE shop.customers ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME shop.customers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: events; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.events (
    id integer NOT NULL,
    happened date NOT NULL
)
PARTITION BY RANGE (happened);


ALTER TABLE shop.events OWNER TO tmp;

--
-- Name: events_2026; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.events_2026 (
    id integer CONSTRAINT events_id_not_null NOT NULL,
    happened date CONSTRAINT events_happened_not_null NOT NULL
);


ALTER TABLE shop.events_2026 OWNER TO tmp;

--
-- Name: graph; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.graph (
    id integer NOT NULL,
    node_key character varying(40),
    parent_id integer
);


ALTER TABLE shop.graph OWNER TO tmp;

--
-- Name: line_items; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.line_items (
    order_id integer NOT NULL,
    line_no integer NOT NULL
);


ALTER TABLE shop.line_items OWNER TO tmp;

--
-- Name: node; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.node (
    key character varying(40) NOT NULL,
    action text,
    edge text
);


ALTER TABLE shop.node OWNER TO tmp;

--
-- Name: paid_customers; Type: VIEW; Schema: shop; Owner: tmp
--

CREATE VIEW shop.paid_customers AS
 SELECT id
   FROM shop.customers
  WHERE (balance > (0)::numeric);


ALTER VIEW shop.paid_customers OWNER TO tmp;

--
-- Name: profiles; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.profiles (
    customer_id bigint NOT NULL,
    bio text
);


ALTER TABLE shop.profiles OWNER TO tmp;

--
-- Name: shipments; Type: TABLE; Schema: shop; Owner: tmp
--

CREATE TABLE shop.shipments (
    id integer NOT NULL,
    order_id integer NOT NULL,
    line_no integer NOT NULL
);


ALTER TABLE shop.shipments OWNER TO tmp;

--
-- Name: events_2026; Type: TABLE ATTACH; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.events ATTACH PARTITION shop.events_2026 FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');


--
-- Name: Order Items id; Type: DEFAULT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop."Order Items" ALTER COLUMN id SET DEFAULT nextval('shop."Order Items_id_seq"'::regclass);


--
-- Name: Order Items Order Items_Customer Id_status_key; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop."Order Items"
    ADD CONSTRAINT "Order Items_Customer Id_status_key" UNIQUE ("Customer Id", status);


--
-- Name: Order Items Order Items_pkey; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop."Order Items"
    ADD CONSTRAINT "Order Items_pkey" PRIMARY KEY (id);


--
-- Name: customers customers_email_key; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.customers
    ADD CONSTRAINT customers_email_key UNIQUE (email);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: graph graph_pkey; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.graph
    ADD CONSTRAINT graph_pkey PRIMARY KEY (id);


--
-- Name: line_items line_items_pkey; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.line_items
    ADD CONSTRAINT line_items_pkey PRIMARY KEY (order_id, line_no);


--
-- Name: node node_pkey; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.node
    ADD CONSTRAINT node_pkey PRIMARY KEY (key);


--
-- Name: profiles profiles_customer_key; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.profiles
    ADD CONSTRAINT profiles_customer_key UNIQUE (customer_id);


--
-- Name: shipments shipments_pkey; Type: CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.shipments
    ADD CONSTRAINT shipments_pkey PRIMARY KEY (id);


--
-- Name: idx_customers_created; Type: INDEX; Schema: shop; Owner: tmp
--

CREATE INDEX idx_customers_created ON shop.customers USING btree (created_at);


--
-- Name: customers customers_touch; Type: TRIGGER; Schema: shop; Owner: tmp
--

CREATE TRIGGER customers_touch BEFORE UPDATE ON shop.customers FOR EACH ROW EXECUTE FUNCTION shop.touch();


--
-- Name: customers customers_referred_by_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.customers
    ADD CONSTRAINT customers_referred_by_fkey FOREIGN KEY (referred_by) REFERENCES shop.customers(id) ON DELETE SET NULL;


--
-- Name: Order Items fk_items_customer; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop."Order Items"
    ADD CONSTRAINT fk_items_customer FOREIGN KEY ("Customer Id") REFERENCES shop.customers(id) ON DELETE CASCADE;


--
-- Name: line_items fk_line_order; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.line_items
    ADD CONSTRAINT fk_line_order FOREIGN KEY (order_id) REFERENCES shop."Order Items"(id);


--
-- Name: shipments fk_ship_line; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.shipments
    ADD CONSTRAINT fk_ship_line FOREIGN KEY (order_id, line_no) REFERENCES shop.line_items(order_id, line_no) MATCH FULL;


--
-- Name: graph graph_node_key_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.graph
    ADD CONSTRAINT graph_node_key_fkey FOREIGN KEY (node_key) REFERENCES shop.node(key);


--
-- Name: graph graph_parent_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.graph
    ADD CONSTRAINT graph_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES shop.graph(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: profiles profiles_customer_id_fkey; Type: FK CONSTRAINT; Schema: shop; Owner: tmp
--

ALTER TABLE ONLY shop.profiles
    ADD CONSTRAINT profiles_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES shop.customers(id);


--
-- PostgreSQL database dump complete
--

\unrestrict jZRPD0ZJR8eqpDuWoaQQAaf9VgECjSXje0Dmip6smpFiClOcFhbJaQEhhulfwnG

