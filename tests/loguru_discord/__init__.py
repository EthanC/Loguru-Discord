from os import environ

from environs import env

env.read_env()

assert environ.get("TESTS_WEBHOOK_URL")
