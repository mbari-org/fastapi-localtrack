# fastapi-localtrack, Apache-2.0 license
# Filename: daemon/__main__.py
# Description: Dispatcher to run jobs and monitor for new models

from dependency_injector.wiring import Provide, inject

from .dispatcher import Dispatcher
from .container import Container


@inject
def main(dispatcher: Dispatcher = Provide[Container.dispatcher]) -> None:
    dispatcher.run()

def run():
    container = Container()
    container.init_resources()
    container.wire(modules=[__name__])
    main()

if __name__ == "__main__":
    run()