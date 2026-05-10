import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;

public class DividerHiddenTest {
    @Test
    void divisionByZeroThrowsIllegalArgumentException() {
        Divider divider = new Divider();

        assertThrows(
            IllegalArgumentException.class,
            () -> divider.divide(10, 0)
        );
    }
}
