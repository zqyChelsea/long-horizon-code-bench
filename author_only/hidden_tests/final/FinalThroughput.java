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

public final class FinalThroughput {

    private static final int ITERATIONS = 12;

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
                .totalTransactionsNumber(4_000_000)
                .targetOrderBookOrdersTotal(15_000)
                .numAccounts(12_000)
                .currenciesAllowed(TestConstants.ALL_CURRENCIES)
                .numSymbols(150)
                .allowedSymbolTypes(ExchangeTestContainer.AllowedSymbolTypes.BOTH)
                .preFillMode(TestOrdersGeneratorConfig.PreFillMode.ORDERS_NUMBER)
                .build());
    }

    @Test
    public void marginSingleSymbol() {
        run(TestDataParameters.singlePairMarginBuilder()
                .totalTransactionsNumber(4_000_000)
                .numAccounts(3_000)
                .build());
    }

    @Test
    public void exchangeSingleSymbol() {
        run(TestDataParameters.singlePairExchangeBuilder()
                .totalTransactionsNumber(4_000_000)
                .numAccounts(3_000)
                .build());
    }

    @Test
    public void mediumMultiSymbol() {
        run(TestDataParameters.builder()
                .totalTransactionsNumber(3_000_000)
                .targetOrderBookOrdersTotal(300_000)
                .numAccounts(1_000_000)
                .currenciesAllowed(TestConstants.ALL_CURRENCIES)
                .numSymbols(5_000)
                .allowedSymbolTypes(ExchangeTestContainer.AllowedSymbolTypes.BOTH)
                .preFillMode(TestOrdersGeneratorConfig.PreFillMode.ORDERS_NUMBER)
                .build());
    }
}

