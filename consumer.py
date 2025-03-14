import os
import logging
import json
from typing import TYPE_CHECKING

import psycopg2
from pika import ConnectionParameters, BlockingConnection
from pika.exceptions import AMQPConnectionError


if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("consumer.log", encoding="utf-8")
    ],
)
DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "host": os.environ.get("DB_HOST"),
    "port": os.environ.get("DB_PORT"),
}

def create_db_table():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logging.info("Connected to the database")

        with conn.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    received_at TIMESTAMP DEFAULT NOW(),
                    tour_id TEXT NOT NULL,
                    status TEXT
                )"""
            )
            conn.commit()
            logging.info("Table 'notifications' checked/created")

        return conn
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logging.info("Connected to the database")
        return conn
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None

connection_params: ConnectionParameters = ConnectionParameters(
    host=os.environ.get("RABBIT_HOST"),
    port=os.environ.get("RABBIT_PORT"),
)

def callback(
    ch: "BlockingChannel",
    method: "Basic.Deliver",
    properties: "BasicProperties",
    body: bytes,
) -> None:
    try:
        data = json.loads(body.decode("utf-8"))
        event_type = data.get("event_type")
        tour_id = data.get("tour_id")
        status = data.get("order_status")

        if not event_type or not tour_id:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO notifications (event_type, tour_id, status) VALUES (%s, %s, %s)",
                        (event_type, tour_id, status),
                    )
                    conn.commit()
                    logging.info("Message saved to database")
            except Exception as e:
                logging.error(f"Database error: {e}")
            finally:
                conn.close()

    except json.JSONDecodeError:
        logging.error("Failed to decode message as JSON")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    try:
        with BlockingConnection(connection_params) as connection:
            with connection.channel() as channel:
                channel.basic_consume(
                    queue="notifications",
                    on_message_callback=callback,
                )
                logging.info("Waiting for messages")
                channel.start_consuming()
    except AMQPConnectionError as e:
        logging.error(f"Failed to connect to RabbitMQ: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")

if __name__ == "__main__":
    create_db_table()
    main()
