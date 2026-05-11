import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class NumberUtilsHiddenTest {
    @Test
    void doubleClampPreservesDecimalsInsideRange() {
        assertEquals(4.75, NumberUtils.clamp(4.75, 0.5, 9.5), 0.000001);
    }

    @Test
    void doubleClampUsesDoubleBounds() {
        assertEquals(0.5, NumberUtils.clamp(-2.0, 0.5, 9.5), 0.000001);
        assertEquals(9.5, NumberUtils.clamp(20.0, 0.5, 9.5), 0.000001);
    }
}
