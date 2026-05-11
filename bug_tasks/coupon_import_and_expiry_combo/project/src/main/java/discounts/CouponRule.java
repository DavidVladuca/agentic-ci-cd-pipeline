package discounts;

import java.time.LocalDate;

public class CouponRule {
    private final int discountCents;
    private final LocalDate expiresOn;

    public CouponRule(int discountCents, LocalDate expiresOn) {
        this.discountCents = discountCents;
        this.expiresOn = expiresOn;
    }

    public int discountCents() {
        return discountCents;
    }

    public boolean isValidOn(LocalDate date) {
        return date.isBefore(expiresOn);
    }
}
