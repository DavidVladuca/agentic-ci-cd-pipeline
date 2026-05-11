import java.time.LocalDateTime;

public class TimeRange {
    private final LocalDateTime start;
    private final LocalDateTime end;

    public TimeRange(LocalDateTime start, LocalDateTime end) {
        if (!start.isBefore(end)) {
            throw new IllegalArgumentException("start must be before end");
        }

        this.start = start;
        this.end = end;
    }

    public boolean overlaps(TimeRange other) {
        return !start.isAfter(other.end) && !end.isBefore(other.start);
    }
}
