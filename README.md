# sm64-eu-to-us-asset-converter
This is a script to convert the assets of the Super Mario 64 EU version into the US once, this project was Vibecoded with opencode Big Pickle, I have still looked over the code but I'm not really a programmer so take that as is.

This script requires Python

So to use this you fist have to get the Super Mario 64 decomp https://github.com/n64decomp/sm64?tab=readme-ov-file jut follow their readme.
After you use it to compile a EU version of the game using you own EU copy, you will notice that it also extracted all the games assets.
Note you run this script via python usually "python ./convert_eu_to_us.py" if you right click in a folder you should have the option to open a terminal window (powershell etc).
Now you have 2 options either throw this script (plus all its files) into your decomp folder (so the script is next to the sm64 folder) and run it,
or you have the scipt in a seperate folder and copy all these files and or entire folders from your extracted assets over and copy them back when its done. (the file list is at the bottom of this readmee)
After doing this you should now be able to compile the US build via the decomp.

Like you see below there are only a few files different and most of them are basically the same.
Pngs are either the same just redecoded or have small differences
sm64 files have differences in timing etc idk how different it actually sounds in practice (this was what ai told me)
the bitdw.bin file is a demo file so just a sequences of button inputs for one of the Demos that plays when waiting on the title screen (based on ai this should be for bowser in the fire sea) its missing in the EU build

Files:
/sm64/levels/ending/cake_eu.png
/sm64/levels/ending/eu_026000.rgba16.png
/sm64/levels/intro/2_eu_copyright.rgba16.png
/sm64/levels/intro/3_eu_tm.rgba16.png
/sm64/levels/menu/main_menu_seg7_eu.0AF80.ia8.png
/sm64/levels/menu/main_menu_seg7_eu.0B640.ia8.png
/sm64/levels/menu/main_menu_seg7_eu.0B680.ia8.png
/sm64/levels/menu/main_menu_seg7_eu.0BDA0.rgba16.png
/sm64/levels/menu/main_menu_seg7_eu.0EDA0.rgba16.png
/sm64/sound/sequences/eu/  all files from here
/sm64/textures/segment2/font_graphics.05F00.ia1.png
/sm64/textures/segment2/font_graphics.060F0.ia1.png
/sm64/textures/segment2/font_graphics.062E0.ia1.png
/sm64/textures/segment2/font_graphics.05F10.ia1.png
/sm64/textures/segment2/font_graphics.06100.ia1.png
/sm64/textures/segment2/font_graphics.062F0.ia1.png
/sm64/textures/segment2/font_graphics.05F20.ia1.png
/sm64/textures/segment2/font_graphics.06110.ia1.png
/sm64/textures/segment2/font_graphics.06300.ia1.png
/sm64/textures/segment2/font_graphics.05F30.ia1.png
/sm64/textures/segment2/font_graphics.06120.ia1.png
/sm64/textures/segment2/font_graphics.06310.ia1.png
/sm64/textures/segment2/font_graphics.05F40.ia1.png
/sm64/textures/segment2/font_graphics.06130.ia1.png
/sm64/textures/segment2/font_graphics.06320.ia1.png
/sm64/textures/segment2/font_graphics.05F50.ia1.png
/sm64/textures/segment2/font_graphics.06140.ia1.png
/sm64/textures/segment2/font_graphics.06330.ia1.png
/sm64/textures/segment2/font_graphics.05F60.ia1.png
/sm64/textures/segment2/font_graphics.06150.ia1.png
/sm64/textures/segment2/font_graphics.06340.ia1.png
/sm64/textures/segment2/font_graphics.05F70.ia1.png
/sm64/textures/segment2/font_graphics.06160.ia1.png
/sm64/textures/segment2/font_graphics.06350.ia1.png
/sm64/textures/segment2/font_graphics.05F80.ia1.png
/sm64/textures/segment2/font_graphics.06170.ia1.png
/sm64/textures/segment2/font_graphics.06360.ia1.png
/sm64/textures/segment2/font_graphics.05F90.ia1.png
/sm64/textures/segment2/font_graphics.06180.ia1.png
/sm64/textures/segment2/font_graphics.06370.ia1.png
/sm64/textures/segment2/font_graphics.05FA0.ia1.png
/sm64/textures/segment2/font_graphics.06190.ia1.png
/sm64/textures/segment2/font_graphics.06380.ia1.png
/sm64/textures/segment2/font_graphics.05FB0.ia1.png
/sm64/textures/segment2/font_graphics.061A0.ia1.png
/sm64/textures/segment2/font_graphics.06390.ia1.png
/sm64/textures/segment2/font_graphics.05FC0.ia1.png
/sm64/textures/segment2/font_graphics.061B0.ia1.png
/sm64/textures/segment2/font_graphics.063A0.ia1.png
/sm64/textures/segment2/font_graphics.05FD0.ia1.png
/sm64/textures/segment2/font_graphics.061C0.ia1.png
/sm64/textures/segment2/font_graphics.063B0.ia1.png
/sm64/textures/segment2/font_graphics.05FE0.ia1.png
/sm64/textures/segment2/font_graphics.061D0.ia1.png
/sm64/textures/segment2/font_graphics.063C0.ia1.png
/sm64/textures/segment2/font_graphics.05FF0.ia1.png
/sm64/textures/segment2/font_graphics.061E0.ia1.png
/sm64/textures/segment2/font_graphics.063D0.ia1.png
/sm64/textures/segment2/font_graphics.06000.ia1.png
/sm64/textures/segment2/font_graphics.061F0.ia1.png
/sm64/textures/segment2/font_graphics.063E0.ia1.png
/sm64/textures/segment2/font_graphics.06010.ia1.png
/sm64/textures/segment2/font_graphics.06200.ia1.png
/sm64/textures/segment2/font_graphics.063F0.ia1.png
/sm64/textures/segment2/font_graphics.06020.ia1.png
/sm64/textures/segment2/font_graphics.06210.ia1.png
/sm64/textures/segment2/font_graphics.06400.ia1.png
/sm64/textures/segment2/font_graphics.06030.ia1.png
/sm64/textures/segment2/font_graphics.06220.ia1.png
/sm64/textures/segment2/font_graphics.06410.ia1.png
/sm64/textures/segment2/font_graphics.06040.ia1.png
/sm64/textures/segment2/font_graphics.06230.ia1.png
/sm64/textures/segment2/font_graphics.06420.ia1.png
/sm64/textures/segment2/font_graphics.06050.ia1.png
/sm64/textures/segment2/font_graphics.06240.ia1.png
/sm64/textures/segment2/font_graphics.06430.ia1.png
/sm64/textures/segment2/font_graphics.06060.ia1.png
/sm64/textures/segment2/font_graphics.06250.ia1.png
/sm64/textures/segment2/font_graphics.06440.ia1.png
/sm64/textures/segment2/font_graphics.06070.ia1.png
/sm64/textures/segment2/font_graphics.06260.ia1.png
/sm64/textures/segment2/font_graphics.06450.ia1.png
/sm64/textures/segment2/font_graphics.06080.ia1.png
/sm64/textures/segment2/font_graphics.06270.ia1.png
/sm64/textures/segment2/font_graphics.06460.ia1.png
/sm64/textures/segment2/font_graphics.06090.ia1.png
/sm64/textures/segment2/font_graphics.06280.ia1.png
/sm64/textures/segment2/font_graphics.06470.ia1.png
/sm64/textures/segment2/font_graphics.060A0.ia1.png
/sm64/textures/segment2/font_graphics.06290.ia1.png
/sm64/textures/segment2/font_graphics.06480.ia1.png
/sm64/textures/segment2/font_graphics.060B0.ia1.png
/sm64/textures/segment2/font_graphics.062A0.ia1.png
/sm64/textures/segment2/font_graphics.06490.ia1.png
/sm64/textures/segment2/font_graphics.060C0.ia1.png
/sm64/textures/segment2/font_graphics.062B0.ia1.png
/sm64/textures/segment2/font_graphics.064A0.ia1.png
/sm64/textures/segment2/font_graphics.060D0.ia1.png
/sm64/textures/segment2/font_graphics.062C0.ia1.png
/sm64/textures/segment2/font_graphics.064B0.ia1.png
/sm64/textures/segment2/font_graphics.060E0.ia1.png
/sm64/textures/segment2/font_graphics.062D0.ia1.png
