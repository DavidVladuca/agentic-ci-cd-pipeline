import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class AppPublicTest {
    @Test
    void sumUpToZeroIsZero() {
        assertEquals(0, App.sumUpTo(0));
    }

    @Test
    void negativeInputThrows() {
        assertThrows(IllegalArgumentException.class, () -> App.sumUpTo(-1));
    }
}