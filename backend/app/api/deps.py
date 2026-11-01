from app.containers.manager import ContainerManager
from app.core import config
from app.database.db import Database
from app.experiments.engine import ExperimentEngine

config.ensure_dirs()
db = Database(config.DB_PATH)
manager = ContainerManager(db)
experiments = ExperimentEngine(db, manager)
