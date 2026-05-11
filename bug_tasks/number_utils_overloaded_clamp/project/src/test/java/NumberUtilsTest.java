import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class NumberUtilsTest {
    @Test
    void clampsIntegers() {
        assertEquals(10, NumberUtils.clamp(99, 0, 10));
        assertEquals(0, NumberUtils.clamp(-5, 0, 10));
        assertEquals(7, NumberUtils.clamp(7, 0, 10));
    }
}
