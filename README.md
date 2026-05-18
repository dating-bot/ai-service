# ai-service

AI pipelines for `dating_bot`:
- `profile.updated` -> analyze bio + generate embedding
- `photo.uploaded` -> NSFW check

Runtime:
- gRPC `Ping` + health service
- RabbitMQ consumer
- Celery worker tasks
