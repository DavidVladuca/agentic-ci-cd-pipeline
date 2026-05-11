import org.junit.jupiter.api.Test;

public class AgeValidatorTest {
    @Test
    void adultAgeDoesNotThrow() {
        AgeValidator validator = new AgeValidator();

        validator.validateAdult(18);
        validator.validateAdult(42);
    }
}
