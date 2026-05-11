import java.util.LinkedHashMap;
import java.util.Map;

public class LruCache<K, V> {
    private final int capacity;
    private final LinkedHashMap<K, V> values = new LinkedHashMap<>();

    public LruCache(int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be positive");
        }

        this.capacity = capacity;
    }

    public V get(K key) {
        return values.get(key);
    }

    public void put(K key, V value) {
        if (values.size() >= capacity) {
            K firstKey = values.keySet().iterator().next();
            values.remove(firstKey);
        }

        values.put(key, value);
    }

    public int size() {
        return values.size();
    }
}
