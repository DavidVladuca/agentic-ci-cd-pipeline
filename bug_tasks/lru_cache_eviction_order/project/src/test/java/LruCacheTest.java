import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class LruCacheTest {
    @Test
    void storesAndRetrievesSingleValue() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);

        assertEquals(1, cache.get("A"));
    }
}
