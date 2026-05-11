package billing;

import discounts.CouponRule;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class InvoiceServiceTest {
    @Test
    void validCouponBeforeExpiryAppliesDiscount() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(200, LocalDate.of(2026, 1, 31));

        assertEquals(
            800,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 1, 1))
        );
    }
}
