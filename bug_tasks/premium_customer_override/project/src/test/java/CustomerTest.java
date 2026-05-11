import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CustomerTest {
    @Test
    void regularCustomerHasNoDiscount() {
        Customer customer = new Customer();

        assertEquals(100.0, customer.finalPrice(100.0), 0.000001);
    }
}
