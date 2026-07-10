from app.edge.contracts import EdgePointBinding, RawPointValue
from app.edge.simulation import simulated_value


class CncAdapter:
    protocol = "cnc"

    def read(self, binding: EdgePointBinding) -> RawPointValue:
        return simulated_value(binding, salt=self.protocol)
