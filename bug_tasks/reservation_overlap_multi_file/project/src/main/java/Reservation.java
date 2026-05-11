public class Reservation {
    private final String roomId;
    private final TimeRange range;

    public Reservation(String roomId, TimeRange range) {
        this.roomId = roomId;
        this.range = range;
    }

    public String roomId() {
        return roomId;
    }

    public TimeRange range() {
        return range;
    }

    public boolean conflictsWith(Reservation other) {
        return range.overlaps(other.range);
    }
}
