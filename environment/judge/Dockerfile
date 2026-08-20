FROM maven:3.9.9-eclipse-temurin-17

RUN groupadd --system judge-runner \
    && useradd --system --gid judge-runner --create-home --home-dir /home/judge-runner judge-runner

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-yaml time \
    && rm -rf /var/lib/apt/lists/*

COPY workspace/exchange-core/ /opt/baseline/
RUN cd /opt/baseline \
    && mvn -B -DskipTests dependency:go-offline \
    && rm -rf /opt/baseline/.git \
    && mkdir -p /home/judge-runner/.m2 \
    && cp -a /root/.m2/. /home/judge-runner/.m2/ \
    && chown -R judge-runner:judge-runner /home/judge-runner/.m2

COPY verifier/ /opt/verifier/
COPY author_only/ /opt/author_only/

RUN chmod -R go-rwx /opt/baseline /opt/verifier /opt/author_only

ENV MAVEN_OPTS="-Xms1g -Xmx12g"
WORKDIR /opt/baseline

ENTRYPOINT ["python3", "/opt/verifier/run_verifier.py"]
