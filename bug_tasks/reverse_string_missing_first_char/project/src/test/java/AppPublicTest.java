import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class AppPublicTest {
    @Test
    void emptyStringReturnsEmptyString() {
        assertEquals("", App.reverse(""));
    }

    @Test
    void nullInputThrows() {
        assertThrows(IllegalArgumentException.class, () -> App.reverse(null));
    }
}