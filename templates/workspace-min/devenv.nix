{ inputs, ... }:
{
  imports = [
    inputs.llm-core.devenvModules.base
  ];
}
