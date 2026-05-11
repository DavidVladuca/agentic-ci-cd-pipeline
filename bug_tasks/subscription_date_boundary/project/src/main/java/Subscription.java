import java.time.LocalDate;

public class Subscription {
    private final LocalDate startDate;
    private final LocalDate expiresOn;

    public Subscription(LocalDate startDate, LocalDate expiresOn) {
        this.startDate = startDate;
        this.expiresOn = expiresOn;
    }

    public boolean isActiveOn(LocalDate date) {
        return !date.isBefore(startDate) && date.isBefore(expiresOn);
    }
}
