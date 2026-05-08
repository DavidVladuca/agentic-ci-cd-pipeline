import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class TransferServiceHiddenTest {
    @Test
    void transferMovesMoneyFromSourceToDestination() {
        Account from = new Account(100);
        Account to = new Account(50);
        TransferService service = new TransferService();

        service.transfer(from, to, 30);

        assertEquals(70, from.getBalance());
        assertEquals(80, to.getBalance());
    }

    @Test
    void zeroTransferDoesNotChangeBalances() {
        Account from = new Account(100);
        Account to = new Account(50);
        TransferService service = new TransferService();

        service.transfer(from, to, 0);

        assertEquals(100, from.getBalance());
        assertEquals(50, to.getBalance());
    }

    @Test
    void tooLargeTransferThrows() {
        Account from = new Account(10);
        Account to = new Account(50);
        TransferService service = new TransferService();

        assertThrows(IllegalArgumentException.class, () -> service.transfer(from, to, 20));
    }
}