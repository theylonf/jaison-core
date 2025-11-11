from utils.logging import setup_logger
setup_logger()

from utils.args import args
from dotenv import load_dotenv
import os

# Carregar .env - se args.env for None, usar o .env na raiz do projeto
if args.env is None:
    env_path = os.path.join(os.getcwd(), '.env')
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(dotenv_path=args.env, override=True)

import asyncio
from utils.server import start_web_server

asyncio.run(start_web_server())