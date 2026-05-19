FROM postgres:16-alpine

# Hardcode max_connections=300 into the image so any orchestrator
# (k8s, docker-compose, swarm) picks it up without manifest changes.
#
# Two layers of hardcoding:
#   1. Patch postgresql.conf.sample so initdb writes the value into
#      $PGDATA/postgresql.conf on a fresh volume.
#   2. CMD adds `-c max_connections=300` so existing volumes (which
#      already have an old postgresql.conf) still get the override.

RUN sed -i 's/^#\?max_connections.*/max_connections = 300/' \
        /usr/local/share/postgresql/postgresql.conf.sample

CMD ["postgres", "-c", "max_connections=300"]
