from sqlalchemy.orm import Session


class BaseService:
    """Base class for all services.

    Services encapsulate business logic and are framework-agnostic:
    no FastAPI Request, Response, or Depends inside service methods.
    The only dependency is a SQLAlchemy Session injected at construction.

    Usage in a router handler:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            service = ExampleService(db)
            return service.do_something()
    """

    def __init__(self, db: Session) -> None:
        self.db = db
