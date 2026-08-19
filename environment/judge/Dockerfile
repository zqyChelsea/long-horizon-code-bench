FROM maven:3.9.9-eclipse-temurin-17

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-yaml \
    && rm -rf /var/lib/apt/lists/*

COPY workspace/exchange-core/ /opt/baseline/
RUN cd /opt/baseline \
    && mvn -B -DskipTests dependency:go-offline \
    && rm -rf /opt/baseline/.git

COPY verifier/ /opt/verifier/
COPY author_only/ /opt/author_only/

RUN chmod -R a-w /opt/baseline /opt/verifier /opt/author_only

ENV MAVEN_OPTS="-Xms1g -Xmx12g"
WORKDIR /opt/baseline

ENTRYPOINT ["python3", "/opt/verifier/run_verifier.py"]

