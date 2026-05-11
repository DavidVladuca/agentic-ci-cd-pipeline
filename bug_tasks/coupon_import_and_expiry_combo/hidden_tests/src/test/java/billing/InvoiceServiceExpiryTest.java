package billing;

import discounts.CouponRule;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class InvoiceServiceExpiryTest {
    @Test
    void couponIsValidOnExpiryDate() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(200, LocalDate.of(2026, 1, 31));

        assertEquals(
            800,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 1, 31))
        );
    }

    @Test
    void expiredCouponDoesNotApplyDiscount() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(200, LocalDate.of(2026, 1, 31));

        assertEquals(
            1000,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 2, 1))
        );
    }

    @Test
    void discountCannotMakeTotalNegative() {
        InvoiceService service = new InvoiceService();
        CouponRule coupon = new CouponRule(5000, LocalDate.of(2026, 1, 31));

        assertEquals(
            0,
            service.totalAfterDiscount(1000, coupon, LocalDate.of(2026, 1, 1))
        );
    }
}
