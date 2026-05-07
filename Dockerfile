FROM maven:3.9.9-eclipse-temurin-17

WORKDIR /workspace

COPY pom.xml /tmp/offline-project/pom.xml
COPY src /tmp/offline-project/src

RUN cd /tmp/offline-project && mvn -B clean test || true

WORKDIR /workspace

CMD ["mvn", "-o", "clean", "test"]