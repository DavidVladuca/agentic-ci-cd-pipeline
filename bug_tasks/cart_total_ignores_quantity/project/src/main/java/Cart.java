import java.util.ArrayList;
import java.util.List;

public class Cart {
    private final List<LineItem> items = new ArrayList<>();

    public void add(LineItem item) {
        if (item == null) {
            throw new IllegalArgumentException("item must not be null");
        }

        items.add(item);
    }

    public int totalCents() {
        int total = 0;

        for (LineItem item : items) {
            total += item.lineTotalCents();
        }

        return total;
    }
}