# Alignment report

PAL functions 34239; other build functions 34166; lined up 33791 (98.7 %).
Named PAL functions carried over: 4383 of 4694.
Hooks (hle_address_map.csv) moved: 443 of 498.
Address map (address_map.csv) entries moved: 541 of 768.
Hand names (names.txt) moved: 3 of 9.

## Not moved: hle_address_map.csv (2)

- 0x80100890 thunk_0x800bc440
- 0x800449C0 OS::ExceptionInit

## Not moved: address_map.csv (122)

- 0x80100890 thunk_0x800bc440
- 0x8003FE20 NAND::Create
- 0x80040020 NAND::Private::CreateAsync
- 0x80040660 NAND::CreateDir
- 0x80040870 NAND::Private::CreateDirAsync
- 0x800449C0 OS::ExceptionInit
- 0x8005DF30 WUDGetStatus
- 0x80061470 DEBUGPrint
- 0x806542C0 
- 0x80654860 
- 0x80662920 
- 0x80662960 
- 0x806629A0 
- 0x806629C0 
- 0x806A1B60 
- 0x8069E1C8 
- 0x8069E210 
- 0x806B5178 
- 0x806B5184 
- 0x806B519C 
- 0x8071E1E0 
- 0x8071E240 
- 0x8075C2B8 
- 0x80769270 
- 0x80769520 
- 0x8070C490 
- 0x8070C510 
- 0x8070CB10 
- 0x8070CB34 
- 0x8070CDE0 
- 0x8070CDE4 
- 0x8070CDE8 
- 0x8070CDF4 
- 0x8070CDF8 
- 0x8070CDFC 
- 0x8070CE60 
- 0x8070D460 
- 0x8070D760 
- 0x8070DB70 
- 0x8070DED8 
- 0x8070E1F0 
- 0x8070E2F0 
- 0x80717E9C 
- 0x80717E9E 
- 0x80717EAA 
- 0x80717EB4 
- 0x80717EC8 
- 0x806F0B10 
- 0x806F0B12 
- 0x806F0B14 
- 0x806F0810 dev/fs_fd
- 0x806F0818 
- 0x806F0928 
- 0x806F0958 
- 0x806F4D48 
- 0x806F4930 
- 0x806F4934 
- 0x806F4964 
- 0x806F4968 
- 0x806F4A14 
- 0x806F4A18 
- 0x806F4AF0 
- 0x806F4AF8 
- 0x806F4AFC 
- 0x806F4B00 
- 0x806F4B04 
- 0x806F4B08 
- 0x806F4B0C 
- 0x806F4B44 
- 0x806F4B48 
- 0x806F4B50 
- 0x806F4B7C 
- 0x806F4B84 
- 0x806F4BD0 
- 0x806F4C00 
- 0x806F4C04 
- 0x806F4C05 
- 0x806F45F0 
- 0x806F45F4 
- 0x806F45FC 
- 0x806F4600 
- 0x806F4604 
- 0x806F4630 
- 0x806F4631 
- 0x806F4640 
- 0x806F4644 
- 0x806F4650 
- 0x806F4658 
- 0x806F466C 
- 0x806F4670 
- 0x806F46A8 
- 0x806F4700 
- 0x806F4758 
- 0x806F4780 
- 0x806F4784 
- 0x806F4788 
- 0x806F479C 
- 0x806F47A0 
- 0x806F47A4 
- 0x806F47A8 
- 0x806F47B0 
- 0x806F4818 
- 0x806F4828 
- 0x806F4834 
- 0x806F4890 
- 0x806F4898 
- 0x806F48A4 
- 0x806F48A8 
- 0x806F48B0 
- 0x806F48D4 
- 0x806F4FDC 
- 0x806F4FE8 
- 0x806F4FEC 
- 0x806F5078 
- 0x806F7038 
- 0x806F703C 
- 0x806F6D40 
- 0x806F8220 
- 0x806F8260 
- 0x806F8280 
- 0x806F82A0 
- 0x806F8410 

## Not moved: names.txt (6)

- 8003FE20 NAND::Create                  # nandIsInitialized, nandIsPrivatePath check, ISFS_CreateFile
- 8003FF30 NAND::Private::Create         # same without the private-path check
- 80040020 NAND::Private::CreateAsync    # ISFS_CreateFileAsync
- 80040660 NAND::CreateDir               # ISFS_CreateDir + private-path check
- 80040770 NAND::Private::CreateDir
- 80040870 NAND::Private::CreateDirAsync # ISFS_CreateDirAsync

