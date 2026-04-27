import logging

from megaqueue.app import create_app
from megaqueue import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

if __name__ == "__main__":
    from waitress import serve

    application = create_app()
    logging.getLogger().info("Starting MegaQueue on %s:%d", config.HOST, config.PORT)
    serve(application, host=config.HOST, port=config.PORT)
