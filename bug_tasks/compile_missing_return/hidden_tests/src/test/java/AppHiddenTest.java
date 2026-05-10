import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class AppHiddenTest {
    @Test
    void zeroValueIsZero() {
        assertEquals("zero", App.sign(0));
    }

    @Test
    void negativeValueIsNegative() {
        assertEquals("negative", App.sign(-4));
    }
}
