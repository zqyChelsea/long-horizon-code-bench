package exchange.core2.tests.perf;

import exchange.core2.core.common.config.InitialStateConfiguration;
import exchange.core2.core.common.config.PerformanceConfiguration;
import exchange.core2.core.common.config.SerializationConfiguration;
import exchange.core2.tests.util.ExchangeTestContainer;
import exchange.core2.tests.util.TestConstants;
import exchange.core2.tests.util.TestDataParameters;
import exchange.core2.tests.util.TestOrdersGeneratorConfig;
import exchange.core2.tests.util.ThroughputTestsModule;
import org.junit.jupiter.api.Test;

public final class FeedbackThroughput {

    private static final int ITERATIONS = 5;

    private static PerformanceConfiguration configuration() {
        return PerformanceConfiguration.throughputPerformanceBuilder()
                .ringBufferSize(32 * 1024)
                .build();
    }

    private static void run(TestDataParameters parameters) {
        ThroughputTestsModule.throughputTestImpl(
                configuration(),
                parameters,
                InitialStateConfiguration.CLEAN_TEST,
                SerializationConfiguration.DEFAULT,
                ITERATIONS);
    }

    @Test
    public void peakMultiSymbol() {
        run(TestDataParameters.builder()
                .totalTransactionsNumber(3_000_000)
                .targetOrderBookOrdersTotal(10_000)
                .numAccounts(10_000)
                .currenciesAllowed(TestConstants.ALL_CURRENCIES)
                .numSymbols(100)
                .allowedSymbolTypes(ExchangeTestContainer.AllowedSymbolTypes.BOTH)
                .preFillMode(TestOrdersGeneratorConfig.PreFillMode.ORDERS_NUMBER)
                .build());
    }

    @Test
    public void marginSingleSymbol() {
        run(TestDataParameters.singlePairMarginBuilder().build());
    }

    @Test
    public void exchangeSingleSymbol() {
        run(TestDataParameters.singlePairExchangeBuilder().build());
    }

    @Test
    public void mediumMultiSymbol() {
        run(TestDataParameters.builder()
                .totalTransactionsNumber(2_000_000)
                .targetOrderBookOrdersTotal(100_000)
                .numAccounts(250_000)
                .currenciesAllowed(TestConstants.ALL_CURRENCIES)
                .numSymbols(2_000)
                .allowedSymbolTypes(ExchangeTestContainer.AllowedSymbolTypes.BOTH)
                .preFillMode(TestOrdersGeneratorConfig.PreFillMode.ORDERS_NUMBER)
                .build());
    }
}

