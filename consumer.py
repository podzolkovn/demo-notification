import logging
import json
from typing import TYPE_CHECKING

import psycopg2
from pika import ConnectionParameters, BlockingConnection


if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.spec import Basic, BasicProperties

logging.basicConfig(
    level=logging.INFO,  # Можно поменять на DEBUG для отладки
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
        logging.FileHandler("consumer.log", encoding="utf-8")  # Лог-файл
    ],
)

DB_CONFIG = {
    "dbname": "queue_db",
    "user": "db_user",
    "password": "db_pass",
    "host": "localhost",
    "port": 5432,
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logging.info("Connected to the database")
        return conn
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return None

connection_params: ConnectionParameters = ConnectionParameters(
    host="localhost",
    port=5672,
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
        status = data.get("order_status")  # Или другой статус, если нужно

        if not event_type or not tour_id:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Подключаемся к БД
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
    with BlockingConnection(connection_params) as connection:
        with connection.channel() as channel:
            queues: list[str] = [
                "order_created",
                "order_updated",
                "order_approved",
                "order_cancelled_by_partner",
                "order_confirmed",
                "order_cancelled",
                "order_ready_for_payment",
                "order_paid",
                "order_not_paid",
                "order_closed",
            ]
            for queue in queues:
                channel.basic_consume(
                    queue=queue,
                    on_message_callback=callback,
                )

            logging.info("Waiting for messages")
            channel.start_consuming()


if __name__ == "__main__":
    main()
