{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    (python312.withPackages (ps: with ps; [
      pyside6
      hidapi
      keyboard
      simpleeval
      certifi
    ]))

    # HID access
    hidapi
    libusb1
  ];

  shellHook = ''
    export PYTHONPATH="src/main/python:$PYTHONPATH"
    echo "Run: python src/main/python/main.py"
  '';
}
