import json
import logging
from pika import ConnectionParameters, BlockingConnection

logging.basicConfig(
    level=logging.INFO,  # Можно поменять на DEBUG для отладки
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
        logging.FileHandler("consumer.log", encoding="utf-8")  # Лог-файл
    ],
)

connection_params: ConnectionParameters = ConnectionParameters(
    host="localhost",
    port=5672,
)


def main():
    data = {
        "event_type": "order_closed",
        "order_id": "678e4567-e89b-12d3-a456-426614174333",
        "tour_id": "123e4567-e89b-12d3-a456-426614174000",
        "order_status": "closed",
        "payment_status": "failed"
    }
    with BlockingConnection(connection_params) as connection:
        with connection.channel() as channel:
            channel.basic_publish(
                exchange="",
                routing_key="order_closed",
                body=json.dumps(data),
            )

            logging.info("[*] Sent %r" % data)

if __name__ == "__main__":
    main()
