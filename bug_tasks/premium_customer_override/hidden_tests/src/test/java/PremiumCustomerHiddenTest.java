import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class PremiumCustomerHiddenTest {
    @Test
    void premiumCustomerGetsTenPercentDiscount() {
        PremiumCustomer customer = new PremiumCustomer();

        assertEquals(0.10, customer.getDiscountRate(), 0.000001);
        assertEquals(90.0, customer.finalPrice(100.0), 0.000001);
    }
}
