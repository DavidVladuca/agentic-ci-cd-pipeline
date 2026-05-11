import java.time.LocalDate;

public class Coupon {
    private final int discountAmount;
    private final LocalDate expiresOn;

    public Coupon(int discountAmount, LocalDate expiresOn) {
        this.discountAmount = discountAmount;
        this.expiresOn = expiresOn;
    }

    public int discountAmount() {
        return discountAmount;
    }

    public boolean isValidOn(LocalDate date) {
        return date.isBefore(expiresOn);
    }
}
