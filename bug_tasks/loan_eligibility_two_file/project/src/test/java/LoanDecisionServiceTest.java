import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;

public class LoanDecisionServiceTest {
    @Test
    void rejectsLowCreditScore() {
        LoanDecisionService service = new LoanDecisionService();

        assertFalse(service.approve(new LoanApplication(650, 10_000, 100_000)));
    }
}
