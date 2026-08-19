FROM maven:3.9.9-eclipse-temurin-17

ARG AGENT_UID=1000
ARG AGENT_GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${AGENT_GID} agent \
    && useradd --uid ${AGENT_UID} --gid ${AGENT_GID} --create-home agent

COPY workspace/exchange-core/ /opt/exchange-core-baseline/

# 依赖在镜像构建阶段缓存，正式任务运行时关闭网络。
RUN cd /opt/exchange-core-baseline \
    && mvn -B -DskipTests dependency:go-offline

RUN mkdir -p /home/workspace/exchange-core /home/feedback /home/submissions \
    && cp -a /opt/exchange-core-baseline/. /home/workspace/exchange-core/ \
    && rm -rf /home/workspace/exchange-core/.git \
    && rm -rf /home/workspace/exchange-core/src/test/java/exchange/core2/tests/perf

COPY task/ /home/task/
COPY spec/ /home/task/spec/
COPY public_tests/ /home/public_tests/
COPY submission/ /home/submit/
COPY policy/ /home/policy/

RUN mkdir -p /home/trajectory /home/agent/.m2 \
    && cp -a /root/.m2/. /home/agent/.m2/ \
    && chmod -R a-w /home/task /home/public_tests /home/submit /home/policy \
    && chmod a+rx /home/public_tests/run_public_tests.sh /home/submit/submit.sh \
    && chmod a+rx /home/policy/command_gateway.py \
    && chmod 700 /home/trajectory \
    && chown -R agent:agent /home/workspace /home/feedback /home/submissions /home/agent/.m2

USER agent
WORKDIR /home/workspace/exchange-core

ENV HOME=/home/agent
ENV MAVEN_OPTS="-Xms1g -Xmx8g"
ENV AGENT_TOOL_POLICY="/home/policy/agent_tools.yaml"

CMD ["sleep", "infinity"]
