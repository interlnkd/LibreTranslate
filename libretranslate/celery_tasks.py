from celery import Celery, Task
import os

class BaseTaskWithDefaultPriority(Task):
    default_priority = 5  # default priority for all tasks

    def apply_async(self, args=None, kwargs=None, **options):
        if 'priority' not in options:
            options['priority'] = self.default_priority
        return super().apply_async(args, kwargs, **options)


celery = Celery(__name__)
celery.conf.broker_url = os.environ.get(
    "CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379")
celery.conf.broker_connection_retry_on_startup = True

celery.conf.update(
    task_concurrency=5,
    worker_heartbeat=120,
)

# 🧠 Enable priority support
celery.conf.broker_transport_options = {
    'queue_order_strategy': 'priority',
    'priority_steps': list(range(10)),
    'sep': ':', 
}

celery.Task = BaseTaskWithDefaultPriority


@celery.task(rate_limit='8/m', name="test_task")
def test_task():
    return True


