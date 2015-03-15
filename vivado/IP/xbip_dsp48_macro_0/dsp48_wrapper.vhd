-- A wrapper around the DSP48E1 macro, presenting a suitable
-- interface to the MyHDL generated code.
-- 

library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;

entity DSP48E1 is
    port (
             A: in signed(24 downto 0);
             B: in signed(17 downto 0);
             C: in signed(47 downto 0);    
             P: out signed(47 downto 0);
             opmode: in unsigned(1 downto 0);
             clock_enable: in std_logic;
             reset: in std_logic;
             clock: in std_logic
         );
end entity DSP48E1;


architecture MyHDL of DSP48E1 is

    component xbip_dsp48_macro_0
        port (
                 CLK : in std_logic;
                 CE : in std_logic;
                 SCLR : in std_logic;
                 SEL : in std_logic_vector(1 downto 0);
                 A : in std_logic_vector(24 downto 0);
                 B : in std_logic_vector(17 downto 0);
                 C : in std_logic_vector(47 downto 0);        
                 P : out std_logic_vector(47 downto 0)
             );
    end component xbip_dsp48_macro_0;
    
    signal wrapped_A: std_logic_vector(24 downto 0);
    signal wrapped_B: std_logic_vector(17 downto 0);
    signal wrapped_C: std_logic_vector(47 downto 0);
    signal wrapped_P: std_logic_vector(47 downto 0);
    signal wrapped_opmode: std_logic_vector(1 downto 0);    
    
begin

    P <= signed(wrapped_P);
    wrapped_A <= std_logic_vector(A);
    wrapped_B <= std_logic_vector(B);
    wrapped_C <= std_logic_vector(C);
    wrapped_opmode <= std_logic_vector(opmode);
    
    dsp_macro : xbip_dsp48_macro_0
    port map (
                 CLK => clock,
                 CE => clock_enable,
                 SCLR => reset,
                 sel => wrapped_opmode,
                 A => wrapped_A,
                 B => wrapped_B,
                 C => wrapped_C,                 
                 P => wrapped_P
             );
    
end architecture MyHDL;
