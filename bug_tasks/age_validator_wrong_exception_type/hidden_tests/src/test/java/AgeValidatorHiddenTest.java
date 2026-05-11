import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;

public class AgeValidatorHiddenTest {
    @Test
    void underageThrowsIllegalArgumentException() {
        AgeValidator validator = new AgeValidator();

        assertThrows(
            IllegalArgumentException.class,
            () -> validator.validateAdult(17)
        );
    }
}
