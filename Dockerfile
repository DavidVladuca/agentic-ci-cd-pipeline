FROM maven:3.9.9-eclipse-temurin-17

ARG USER_ID=10001
ARG GROUP_ID=10001

# create a non-root user for running untrusted generated/repaired code
RUN groupadd --gid ${GROUP_ID} agent \
    && useradd --uid ${USER_ID} --gid ${GROUP_ID} --create-home --shell /usr/sbin/nologin agent

WORKDIR /dependency-cache

# copy the agent project's pom only to pre-cache the Maven/JUnit dependencies used by sandbox tasks
COPY --chown=agent:agent pom.xml ./pom.xml

# Docker creates WORKDIR as root, so give the non-root user ownership before switching users
RUN chown -R agent:agent /dependency-cache /home/agent

USER agent

RUN mkdir -p /home/agent/.m2/repository

# force Maven to download compiler/surefire/JUnit dependencies during image build
# this makes later Docker runs work with --network none and mvn -o
RUN mkdir -p src/main/java src/test/java \
    && printf 'public class App { public static int add(int a, int b) { return a + b; } }\n' > src/main/java/App.java \
    && printf 'import org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.assertEquals;\npublic class AppTest { @Test void addWorks() { assertEquals(5, App.add(2, 3)); } }\n' > src/test/java/AppTest.java \
    && mvn -B -q -Dmaven.repo.local=/home/agent/.m2/repository clean test \
    && rm -rf src target

ENV HOME=/tmp
ENV MAVEN_CONFIG=/tmp/.m2
ENV MAVEN_OPTS="-Dstyle.color=never"

WORKDIR /workspace