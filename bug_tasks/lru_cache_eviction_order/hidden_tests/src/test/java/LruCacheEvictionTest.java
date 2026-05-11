import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

public class LruCacheEvictionTest {
    @Test
    void getRefreshesRecencyBeforeEviction() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);
        cache.put("B", 2);
        assertEquals(1, cache.get("A"));

        cache.put("C", 3);

        assertEquals(1, cache.get("A"));
        assertNull(cache.get("B"));
        assertEquals(3, cache.get("C"));
    }

    @Test
    void updatingExistingKeyDoesNotEvictOtherEntry() {
        LruCache<String, Integer> cache = new LruCache<>(2);

        cache.put("A", 1);
        cache.put("B", 2);
        cache.put("A", 10);

        assertEquals(2, cache.size());
        assertEquals(10, cache.get("A"));
        assertEquals(2, cache.get("B"));
    }
}
