import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class AppHiddenTest {
    @Test
    void allNegativeArrayReturnsLeastNegativeValue() {
        assertEquals(-2, App.max(new int[] {-8, -2, -5}));
    }

    @Test
    void singleNegativeValueWorks() {
        assertEquals(-10, App.max(new int[] {-10}));
    }

    @Test
    void mixedArrayReturnsLargestValue() {
        assertEquals(4, App.max(new int[] {-10, 4, -1}));
    }
}