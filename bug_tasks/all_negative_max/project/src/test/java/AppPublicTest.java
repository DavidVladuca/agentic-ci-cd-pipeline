import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class AppPublicTest {
    @Test
    void positiveArrayReturnsLargestValue() {
        assertEquals(9, App.max(new int[] {1, 9, 3}));
    }

    @Test
    void emptyArrayThrows() {
        assertThrows(IllegalArgumentException.class, () -> App.max(new int[] {}));
    }

    @Test
    void nullArrayThrows() {
        assertThrows(IllegalArgumentException.class, () -> App.max(null));
    }
}