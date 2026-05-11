import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

public class LoanDecisionScenarioTest {
    @Test
    void creditScoreExactlySevenHundredIsEligible() {
        LoanDecisionService service = new LoanDecisionService();

        assertTrue(service.approve(new LoanApplication(700, 20_000, 100_000)));
    }

    @Test
    void highDebtRatioIsRejectedUsingDecimalArithmetic() {
        LoanDecisionService service = new LoanDecisionService();

        assertFalse(service.approve(new LoanApplication(720, 50_000, 100_000)));
    }

    @Test
    void ratioAtFortyPercentIsAccepted() {
        LoanDecisionService service = new LoanDecisionService();

        assertTrue(service.approve(new LoanApplication(720, 40_000, 100_000)));
    }
}
