#!/usr/bin/env bash
set -euo pipefail

workspace="${WORKSPACE_DIR:-/home/workspace/exchange-core}"
cd "$workspace"

echo "[1/3] 编译生产代码"
mvn -B -o -DskipTests package

echo "[2/3] 运行订单簿公开测试"
mvn -B -o test -Dtest='OrderBookDirectImplTest,OrderBookDirectImplExchangeTest,OrderBookDirectImplMarginTest'

echo "[3/3] 运行基础集成与拒绝路径测试"
mvn -B -o test -Dtest='ITExchangeCoreIntegrationBasic,ITExchangeCoreIntegrationRejectionBasic,ITMultiOperation,SimpleEventsProcessorTest'

echo "PUBLIC_TESTS_OK=1"
