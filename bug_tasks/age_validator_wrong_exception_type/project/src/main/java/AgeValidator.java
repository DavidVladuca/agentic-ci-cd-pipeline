public class AgeValidator {
    public void validateAdult(int age) {
        if (age < 18) {
            throw new RuntimeException("underage");
        }
    }
}
